from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import COORDINATOR, ORGANISER, insert_event

# ORGANISER is org-1 of client organisation o1.
COLLEAGUE = {"userId": "org-2", "organisationId": "o1", "role": "organiser", "userName": "Evan"}
OUTSIDER = {"userId": "org-9", "organisationId": "o2", "role": "organiser", "userName": "Dana"}
NO_ORGANISATION = {"userId": "org-solo", "organisationId": None, "role": "organiser", "userName": "Solo"}
REFUSAL = "You can only open your own organisation's events."
HEADERS = {"Authorization": "Bearer token"}


class OrganisationAccessCase(ServiceTestCase):
    """SPM-47: an organiser reaches only their own client organisation's events."""

    caller = ORGANISER

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.routers.event.resolve_caller", side_effect=lambda *args, **kwargs: self.caller),
            patch("app.routers.event.current_organiser", side_effect=lambda *args, **kwargs: self.caller),
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_followup.registration_count", return_value=0),
            patch("app.services.event_followup._soft_get", return_value={}),
            patch("app.services.event_followup.list_users", return_value=[]),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)
        self.client.__enter__()
        # o1: mine (submitted, draft, discarded, completed), a colleague's (planning, draft).
        insert_event(self.db, eventId="my-request", organiserId="org-1", organisationId="o1", status="submitted")
        insert_event(self.db, eventId="my-draft", organiserId="org-1", organisationId="o1", status="draft")
        insert_event(self.db, eventId="my-discarded", organiserId="org-1", organisationId="o1", status="discarded")
        insert_event(self.db, eventId="my-past", organiserId="org-1", organisationId="o1", status="completed")
        insert_event(self.db, eventId="colleagues", organiserId="org-2", organisationId="o1", status="planning")
        insert_event(self.db, eventId="colleagues-draft", organiserId="org-2", organisationId="o1", status="draft")
        # o2: another client organisation.
        insert_event(self.db, eventId="theirs", organiserId="org-9", organisationId="o2", status="planning")
        insert_event(self.db, eventId="theirs-confirmed", organiserId="org-9", organisationId="o2", status="confirmed")
        insert_event(self.db, eventId="solo", organiserId="org-solo", organisationId=None, status="submitted")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for item in reversed(self.patches):
            item.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def get(self, path):
        return self.client.get(path, headers=HEADERS)

    def ids(self, path):
        response = self.get(path)
        self.assertEqual(response.status_code, 200, response.text)
        return {row["eventId"] for row in response.json()}


class TestOverview(OrganisationAccessCase):
    """AC1 and AC2: the overview lists the organisation's requests and past records, every
    organiser in it sees them, and only the caller's own drafts are listed with them."""

    def test_the_overview_lists_the_organisations_events_and_only_my_own_drafts(self):
        self.assertEqual(self.ids("/events/mine"), {"my-request", "my-draft", "my-past", "colleagues"})

    def test_a_colleague_sees_the_same_organisation_events_on_their_dashboard(self):
        self.caller = COLLEAGUE

        self.assertEqual(self.ids("/events/mine"), {"my-request", "my-past", "colleagues", "colleagues-draft"})

    def test_another_organisations_organiser_sees_none_of_them(self):
        self.caller = OUTSIDER

        self.assertEqual(self.ids("/events/mine"), {"theirs", "theirs-confirmed"})

    def test_an_organiser_with_no_organisation_sees_only_their_own_events(self):
        self.caller = NO_ORGANISATION

        self.assertEqual(self.ids("/events/mine"), {"solo"})

    def test_event_lists_are_limited_to_the_organisation_for_organisers_and_whole_for_staff(self):
        self.caller = OUTSIDER
        self.assertEqual(self.ids("/events"), {"theirs", "theirs-confirmed"})
        self.assertEqual(self.ids("/events/all"), {"theirs", "theirs-confirmed"})
        self.assertEqual(self.ids("/events/confirmed"), {"theirs-confirmed"})
        self.caller = COORDINATOR
        self.assertTrue({"theirs", "colleagues", "my-request", "solo"} <= self.ids("/events"))


class TestOpeningAnEvent(OrganisationAccessCase):
    """AC3 (another organisation's event URL is 403) and AC4 (own organisation and staff still open)."""

    def test_another_organisations_event_page_and_record_are_403(self):
        for path in ("/events/theirs", "/events/theirs/activity-log", "/events/theirs/readiness",
                     "/events/theirs/readiness-items/any-item",
                     "/events/theirs/attendee-card"):
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual((response.status_code, response.json()["detail"]), (403, REFUSAL))

    def test_organisers_open_their_own_and_their_colleagues_events(self):
        for path in ("/events/my-request", "/events/colleagues", "/events/colleagues/activity-log",
                     "/events/colleagues/readiness", "/events/colleagues/attendee-card"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 200)

    def test_staff_open_any_organisations_event(self):
        self.caller = COORDINATOR
        for path in ("/events/theirs", "/events/theirs/activity-log", "/events/theirs/readiness"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 200)

    def test_a_confirmed_events_public_page_stays_open_to_any_organiser(self):
        # The public page holds only what attendees see once an event is confirmed (boundary).
        self.assertEqual(self.get("/events/theirs-confirmed/attendee-card").status_code, 200)
        self.assertEqual(self.get("/events/theirs-confirmed").status_code, 403)

    def test_an_organiser_with_no_organisation_opens_only_their_own_event(self):
        self.caller = NO_ORGANISATION

        self.assertEqual(self.get("/events/solo").status_code, 200)
        self.assertEqual(self.get("/events/my-request").status_code, 403)

    def test_an_unknown_event_is_still_404(self):
        self.assertEqual(self.get("/events/nope").status_code, 404)
