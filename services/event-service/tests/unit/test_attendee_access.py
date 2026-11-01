from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import registered_event_ids
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import COORDINATOR, ORGANISER, insert_event

ATTENDEE = {"userId": "att-1", "role": "attendee", "userName": "Amy"}
REFUSAL = "Attendees can open only confirmed event pages and their own registrations."
HEADERS = {"Authorization": "Bearer token"}
# Fields only staff or the organiser may see; none is on the attendee's card.
INTERNAL_FIELDS = {"internalNotes", "coordinatorId", "organiserId", "organisationId", "equipmentLines", "venueRequirements"}


class AttendeeAccessCase(ServiceTestCase):
    """SPM-127: what a signed-in attendee can open on event-service."""

    caller = ATTENDEE

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.routers.event.resolve_caller", side_effect=lambda *args, **kwargs: self.caller),
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_followup.registration_count", return_value=0),
            patch("app.services.event_followup._soft_get", return_value={}),
            patch("app.routers.event.registered_event_ids", return_value=set()),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        insert_event(self.db, eventId="e-open", status="confirmed", registrationEnabled=True, internalNotes="Staff only")
        insert_event(self.db, eventId="e-planning", status="planning", internalNotes="Staff only")
        insert_event(self.db, eventId="e-cancelled", status="cancelled")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def get(self, path):
        return self.client.get(path, headers=HEADERS)


class TestStaffAndOrganiserPagesRefuseAttendees(AttendeeAccessCase):
    """AC2 and AC3: the full event record, the lists of events and the activity log are
    staff or organiser pages, so an attendee gets 403 there, enforced on the server."""

    def test_every_staff_or_organiser_event_page_is_403_for_an_attendee(self):
        for path in ["/events", "/events/all", "/events/confirmed", "/events/e-open", "/events/e-planning",
                     "/events/e-open/activity-log"]:
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual((response.status_code, response.json()["detail"]), (403, REFUSAL))

    def test_staff_and_organisers_still_open_them(self):
        for caller in (COORDINATOR, ORGANISER):
            self.caller = caller
            for path in ["/events", "/events/all", "/events/confirmed", "/events/e-planning", "/events/e-open/activity-log"]:
                with self.subTest(role=caller["role"], path=path):
                    self.assertEqual(self.get(path).status_code, 200)


class TestAttendeeCard(AttendeeAccessCase):
    """AC1: an attendee opens the public page of a confirmed event, or of an event they
    hold a registration for; AC2: the page carries public details only."""

    def test_a_confirmed_event_page_opens_with_public_details_only(self):
        response = self.get("/events/e-open/attendee-card")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "confirmed")
        self.assertTrue(response.json()["registrationEnabled"])
        self.assertIn("registrationOpensAt", response.json())
        self.assertFalse(INTERNAL_FIELDS & set(response.json()))

    def test_an_event_not_yet_confirmed_is_403_unless_the_attendee_registered(self):
        refused = self.get("/events/e-planning/attendee-card")
        self.assertEqual((refused.status_code, refused.json()["detail"]), (403, REFUSAL))

    def test_a_cancelled_event_the_attendee_registered_for_still_opens(self):
        with patch("app.routers.event.registered_event_ids", return_value={"e-cancelled"}):
            response = self.get("/events/e-cancelled/attendee-card")

        self.assertEqual((response.status_code, response.json()["status"]), (200, "cancelled"))

    def test_another_events_registration_does_not_open_it(self):
        with patch("app.routers.event.registered_event_ids", return_value={"e-open"}):
            response = self.get("/events/e-cancelled/attendee-card")

        self.assertEqual(response.status_code, 403)

    def test_registrations_are_only_checked_for_an_event_that_is_not_confirmed(self):
        with patch("app.routers.event.registered_event_ids") as lookup:
            self.get("/events/e-open/attendee-card")

        lookup.assert_not_called()

    def test_staff_open_the_card_at_any_status_without_a_registration_check(self):
        self.caller = COORDINATOR
        with patch("app.routers.event.registered_event_ids") as lookup:
            response = self.get("/events/e-planning/attendee-card")

        self.assertEqual(response.status_code, 200)
        lookup.assert_not_called()

    def test_an_unknown_event_is_404(self):
        self.assertEqual(self.get("/events/nope/attendee-card").status_code, 404)


class TestRegisteredEventIds(ServiceTestCase):
    """The client that asks registration-service which events the caller is registered for."""

    def client_returning(self, response=None, error=None):
        client = MagicMock()
        if error:
            client.get.side_effect = error
        else:
            client.get.return_value = response
        return patch("app.orchestration.clients._registration_client", client), client

    def test_returns_the_event_ids_and_forwards_the_token(self):
        response = MagicMock(status_code=200)
        response.json.return_value = ["e1", "e8"]
        stub, client = self.client_returning(response)
        with stub:
            ids = registered_event_ids("Bearer token")

        self.assertEqual(ids, {"e1", "e8"})
        self.assertTrue(client.get.call_args.args[0].endswith("/registrations/mine/event-ids"))
        self.assertEqual(client.get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_an_unreachable_or_failing_service_is_503(self):
        for stub, _client in (
            self.client_returning(error=httpx.ConnectError("down")),
            self.client_returning(MagicMock(status_code=500)),
        ):
            with stub, self.assertRaises(HTTPException) as ctx:
                registered_event_ids(None)
            self.assertEqual(ctx.exception.status_code, 503)
