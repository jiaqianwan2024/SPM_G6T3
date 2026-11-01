"""SPM-88: an organiser or the assigned coordinator cancels an event, and its arrangements are released."""

from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.event import Event
from app.models.event_change_request import EventChangeRequest
from app.orchestration import clients
from app.orchestration.clients import ReleaseFailed
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import service_unavailable
from tests.unit.support import COORDINATOR, ORGANISER, EventCase, insert_event

SERVICE = "app.services.event_service"
TOKEN = "Bearer token"
VENUE = [
    {"bookingId": "vb-1", "previousStatus": "approved", "reviewedBy": "u-vinod"},
    {"bookingId": "vb-2", "previousStatus": "pending", "reviewedBy": None},
]
EQUIPMENT = [{"reservationId": "er-1", "previousStatus": "active", "handledBy": "u-tia"}]
LIVE = (
    "submitted", "under review", "changes requested", "approved", "planning",
    "safety review", "safety approved", "preparing", "prepared", "confirmed", "reconsidering",
)


class CancelCase(EventCase):
    def setUp(self):
        super().setUp()
        self.mocks = {}
        for name, value in {
            "release_venue_for_cancellation": VENUE,
            "release_equipment_for_cancellation": EQUIPMENT,
            "restore_venue_after_failed_cancellation": True,
            "restore_equipment_after_failed_cancellation": True,
            "registered_attendees": [{"userId": "u-amy"}, {"userId": None}],
            # Not under test; without it each reply waits on user-service.
            "organisation_names": {},
        }.items():
            patcher = patch(f"{SERVICE}.{name}", return_value=value)
            self.mocks[name] = patcher.start()
            self.addCleanup(patcher.stop)
        insert_event(self.db, eventId="e1", status="planning", coordinatorId="coord-1", eventName="AI Summit")

    def cancel(self, caller=ORGANISER, event_id="e1", reason="Speaker withdrew"):
        return self.service.cancel_event(event_id, reason, caller, TOKEN)

    def stored(self, event_id="e1"):
        self.db.expire_all()
        return self.db.get(Event, event_id)

    def refused(self, call):
        with self.assertRaises(HTTPException) as ctx:
            call()
        return ctx.exception


class TestWhoAndWhen(CancelCase):
    def test_ac1_the_organiser_and_the_assigned_coordinator_can_cancel(self):
        insert_event(self.db, eventId="e2", status="confirmed", coordinatorId="coord-1")

        self.assertEqual(self.cancel(ORGANISER).status, "cancelled")
        self.assertEqual(self.cancel(COORDINATOR, event_id="e2").status, "cancelled")

    def test_ac1_another_organisation_another_coordinator_or_other_staff_are_refused(self):
        outsider = {"userId": "org-9", "organisationId": "o2", "role": "organiser"}
        other_coordinator = {"userId": "coord-2", "role": "coordinator"}
        for caller in (outsider, other_coordinator, {"userId": "lead", "role": "coordinatorlead"}):
            with self.subTest(caller=caller["userId"]):
                self.assertEqual(self.refused(lambda: self.cancel(caller)).status_code, 403)
        self.mocks["release_venue_for_cancellation"].assert_not_called()

    def test_every_live_status_can_be_cancelled(self):
        for index, status in enumerate(LIVE):
            insert_event(self.db, eventId=f"live-{index}", status=status)
            with self.subTest(status=status):
                self.assertEqual(self.cancel(event_id=f"live-{index}").status, "cancelled")

    def test_ac4_a_closed_event_cannot_be_cancelled_and_cancelled_is_terminal(self):
        self.cancel()
        for index, status in enumerate(("draft", "discarded", "rejected", "completed")):
            insert_event(self.db, eventId=f"closed-{index}", status=status)
            with self.subTest(status=status):
                refused = self.refused(lambda: self.cancel(event_id=f"closed-{index}"))
                self.assertEqual((refused.status_code, refused.detail), (409, f"A {status} event cannot be cancelled."))
        self.assertEqual(self.refused(lambda: self.cancel()).status_code, 409)


class TestCancelling(CancelCase):
    def test_ac2_ac10_it_takes_effect_at_once_and_keeps_the_reason_who_and_when(self):
        cancelled = self.cancel()

        self.assertEqual(
            (cancelled.status, cancelled.cancellationReason, cancelled.cancelledBy), ("cancelled", "Speaker withdrew", "org-1")
        )
        self.assertIsNotNone(self.stored().cancelledAt)

    def test_ac5_ac6_the_venue_and_equipment_are_released_with_the_reason(self):
        self.cancel()

        self.mocks["release_venue_for_cancellation"].assert_called_once_with("e1", TOKEN)
        self.mocks["release_equipment_for_cancellation"].assert_called_once_with("e1", "Speaker withdrew", TOKEN)

    def test_ac10_the_cancellation_is_in_the_activity_log(self):
        self.cancel()

        log = self.service.get_activity_log("e1")

        cancel_row = [row for row in log if row.kind == "status" and row.toStatus == "cancelled"][-1]
        self.assertEqual((cancel_row.fromStatus, cancel_row.changedBy, cancel_row.note), ("planning", "org-1", "Cancelled: Speaker withdrew"))

    def test_ac11_a_pending_change_request_is_closed_and_a_decided_one_is_left(self):
        for request_id, status in (("cr-open", "pending"), ("cr-done", "declined")):
            self.db.add(EventChangeRequest(changeRequestId=request_id, eventId="e1", requestedBy="org-1", status=status))
        self.db.commit()

        self.cancel()

        rows = {row.changeRequestId: row for row in self.db.query(EventChangeRequest).all()}
        self.assertEqual((rows["cr-open"].status, rows["cr-open"].reviewedBy), ("closed", "org-1"))
        self.assertEqual(rows["cr-open"].decisionReason, "The event was cancelled: Speaker withdrew")
        self.assertEqual(rows["cr-done"].status, "declined")


class TestNotifying(CancelCase):
    def recipients(self):
        call = self.published.call_args
        return call.args[0], call.args[3], call.args[4], call.kwargs["actor_id"]

    def test_ac7_ac8_attendees_and_the_staff_involved_are_told_the_reason(self):
        self.cancel()

        trigger, recipients, context, actor = self.recipients()
        self.assertEqual((trigger, context, actor), ("event.cancelled", {"eventName": "AI Summit", "reason": "Speaker withdrew"}, "org-1"))
        self.assertCountEqual(
            recipients,
            [
                {"userId": "coord-1", "role": "coordinator"},
                {"userId": "org-1", "role": "organiser"},
                {"userId": "u-vinod", "role": "venue"},
                {"userId": "u-tia", "role": "techsupport"},
                {"userId": "u-amy", "role": "attendee"},
            ],
        )

    def test_with_no_coordinator_and_attendees_that_cannot_be_read_the_rest_are_still_told(self):
        insert_event(self.db, eventId="e-solo", status="submitted", coordinatorId=None)
        self.mocks["registered_attendees"].side_effect = service_unavailable("down")

        self.cancel(event_id="e-solo")

        self.assertEqual(
            {(row["userId"], row["role"]) for row in self.recipients()[1]},
            {("org-1", "organiser"), ("u-vinod", "venue"), ("u-tia", "techsupport")},
        )


class TestAllOrNothing(CancelCase):
    """AC9: if any release fails, the event and its arrangements never disagree."""

    def test_a_venue_release_that_fails_gives_the_equipment_back(self):
        self.mocks["release_venue_for_cancellation"].side_effect = ReleaseFailed("venue release")

        refused = self.refused(self.cancel)

        self.assertEqual(refused.status_code, 503)
        self.assertIn("its venue bookings could not be released. Everything already released was given back", refused.detail)
        self.mocks["restore_equipment_after_failed_cancellation"].assert_called_once_with("e1", EQUIPMENT, TOKEN)
        self.mocks["restore_venue_after_failed_cancellation"].assert_not_called()
        self.assertEqual(self.stored().status, "planning")
        self.published.assert_not_called()

    def test_an_equipment_release_that_fails_gives_the_venue_back(self):
        self.mocks["release_equipment_for_cancellation"].side_effect = ReleaseFailed("equipment release")

        refused = self.refused(self.cancel)

        self.assertEqual(refused.status_code, 503)
        self.assertIn("its equipment could not be released. Everything already released was given back", refused.detail)
        self.mocks["restore_venue_after_failed_cancellation"].assert_called_once_with("e1", VENUE, TOKEN)
        self.mocks["restore_equipment_after_failed_cancellation"].assert_not_called()
        self.assertEqual(self.stored().status, "planning")

    def test_when_both_releases_fail_there_is_nothing_to_give_back(self):
        self.mocks["release_venue_for_cancellation"].side_effect = ReleaseFailed("venue release")
        self.mocks["release_equipment_for_cancellation"].side_effect = ReleaseFailed("equipment release")

        refused = self.refused(self.cancel)

        self.assertIn("its venue bookings and equipment could not be released. Everything", refused.detail)
        self.mocks["restore_venue_after_failed_cancellation"].assert_not_called()
        self.mocks["restore_equipment_after_failed_cancellation"].assert_not_called()

    def test_when_the_undo_fails_too_the_user_is_told_to_contact_staff(self):
        self.mocks["release_equipment_for_cancellation"].side_effect = ReleaseFailed("equipment release")
        self.mocks["restore_venue_after_failed_cancellation"].return_value = False

        refused = self.refused(self.cancel)

        self.assertIn("could not be given back. Please contact Venue Staff and Technical Support.", refused.detail)

    def test_a_cancellation_that_cannot_be_saved_gives_both_releases_back(self):
        with patch.object(self.db, "commit", side_effect=RuntimeError("database gone")):
            refused = self.refused(self.cancel)

        self.assertIn("it could not be saved. Everything already released was given back", refused.detail)
        self.mocks["restore_equipment_after_failed_cancellation"].assert_called_once_with("e1", EQUIPMENT, TOKEN)
        self.mocks["restore_venue_after_failed_cancellation"].assert_called_once_with("e1", VENUE, TOKEN)
        self.assertEqual(self.stored().status, "planning")
        self.published.assert_not_called()

    def test_if_either_undo_fails_after_a_failed_save_the_user_is_told(self):
        self.mocks["restore_equipment_after_failed_cancellation"].return_value = False
        with patch.object(self.db, "commit", side_effect=RuntimeError("database gone")):
            refused = self.refused(self.cancel)

        self.assertIn("could not be given back", refused.detail)


class TestCancelRoute(CancelCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = ORGANISER
        gate = patch("app.routers.event.resolve_caller", side_effect=lambda *args, **kwargs: self.caller)
        self.gate = gate.start()
        self.addCleanup(gate.stop)
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, body):
        return self.client.post("/events/e1/cancel", headers={"Authorization": TOKEN}, json=body)

    def test_ac2_a_reason_is_required(self):
        for body in ({}, {"reason": "   "}):
            with self.subTest(body=body):
                self.assertEqual(self.post(body).status_code, 422)
        self.assertEqual(self.stored().status, "planning")

    def test_the_organiser_cancels_through_the_route_with_no_approval_step(self):
        response = self.post({"reason": "  Speaker withdrew  "})

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()["status"], response.json()["cancellationReason"]), ("cancelled", "Speaker withdrew"))
        self.assertEqual(self.gate.call_args.kwargs["allowed_roles"], {"organiser", "coordinator"})
        # The notice is sent just after the reply.
        self.assertEqual(self.published.call_args.args[0], "event.cancelled")


class TestCancellationClients(EventCase):
    """The calls a cancellation makes to venue- and equipment-service."""

    def reply(self, status_code=200, body=None):
        response = MagicMock(status_code=status_code)
        response.json.return_value = [] if body is None else body
        return patch("app.orchestration.clients.httpx.post", return_value=response)

    def test_releases_post_the_event_with_the_callers_token_and_return_what_was_freed(self):
        with self.reply(body=VENUE) as post:
            self.assertEqual(clients.release_venue_for_cancellation("e1", TOKEN), VENUE)
        self.assertTrue(post.call_args.args[0].endswith("/venues/bookings/release"))
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": TOKEN})
        with self.reply(body=EQUIPMENT) as post:
            self.assertEqual(clients.release_equipment_for_cancellation("e1", "Rain", TOKEN), EQUIPMENT)
        self.assertEqual(post.call_args.kwargs["json"], {"eventId": "e1", "reason": "The event was cancelled: Rain"})

    def test_a_refused_or_unreachable_release_raises(self):
        with self.reply(status_code=403), self.assertRaises(ReleaseFailed):
            clients.release_venue_for_cancellation("e1", None)
        with patch("app.orchestration.clients.httpx.post", side_effect=httpx.ConnectError("down")), self.assertRaises(ReleaseFailed):
            clients.release_equipment_for_cancellation("e1", "Rain", TOKEN)

    def test_the_undo_sends_back_each_previous_status_and_says_whether_it_worked(self):
        with self.reply() as post:
            self.assertTrue(clients.restore_venue_after_failed_cancellation("e1", VENUE, TOKEN))
        self.assertEqual(
            post.call_args.kwargs["json"]["bookings"],
            [{"bookingId": "vb-1", "status": "approved"}, {"bookingId": "vb-2", "status": "pending"}],
        )
        with self.reply() as post:
            self.assertTrue(clients.restore_equipment_after_failed_cancellation("e1", EQUIPMENT, TOKEN))
        self.assertEqual(post.call_args.kwargs["json"]["reservations"], [{"reservationId": "er-1", "status": "active"}])
        with self.reply(status_code=503):
            self.assertFalse(clients.restore_venue_after_failed_cancellation("e1", VENUE, TOKEN))
            self.assertFalse(clients.restore_equipment_after_failed_cancellation("e1", EQUIPMENT, TOKEN))

    def test_nothing_released_means_nothing_to_undo(self):
        with patch("app.orchestration.clients.httpx.post") as post:
            self.assertTrue(clients.restore_venue_after_failed_cancellation("e1", [], TOKEN))
            self.assertTrue(clients.restore_equipment_after_failed_cancellation("e1", [], TOKEN))
        post.assert_not_called()
