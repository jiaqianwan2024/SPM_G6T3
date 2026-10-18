from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.models.event_review import EventReview
from app.schemas.event import EventAssignmentCreate, EventRejection
from tests.unit.support import EventCase, draft_payload, event_create, insert_event


def rejection(reason="no suitable venue available", explanation="No hall fits those dates."):
    return EventRejection(reason=reason, explanation=explanation)


class TestEventDecisions(EventCase):
    def reject(self, event_id, coordinator_id="coord-1", data=None, directory=None):
        """Reject with the three outbound calls patched, returning the result and the mocks."""
        with patch("app.services.event_service.release_event_venue_bookings") as venues, patch(
            "app.services.event_service.release_event_holds"
        ) as equipment, patch("app.services.event_service.send_notification", return_value=True) as sent, patch(
            "app.services.event_service.list_users", return_value=directory or []
        ):
            result = self.service.reject_event(event_id, coordinator_id, data or rejection(), "Bearer token")
        return result, venues, equipment, sent

    def test_missing_event_is_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_event("missing")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_assign_coordinator_stores_the_assignment(self):
        created = self.service.create_event(event_create(), "org-1", "o1")
        directory = [{"userId": "coord-1", "userName": "Ben", "email": "ben@example.com", "role": "coordinator"}]

        with patch("app.services.event_service.list_users", return_value=directory), patch(
            "app.services.event_service.send_notification", return_value=True
        ):
            assignment = self.service.assign_coordinator(
                created.eventId, EventAssignmentCreate(coordinatorId="coord-1"), "coord-1"
            )

        self.assertEqual(assignment.coordinatorId, "coord-1")
        self.assertEqual(assignment.assignedBy, "coord-1")
        self.assertEqual(self.service.get_event(created.eventId).status, "under review")

    def test_assign_coordinator_is_404_when_the_event_is_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.assign_coordinator("missing", EventAssignmentCreate(coordinatorId="coord-1"), "coord-1")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_approve_event_moves_an_assigned_request_under_review_to_planning(self):
        insert_event(self.db, eventId="e-review", status="under review", coordinatorId="coord-1")

        with patch("app.services.event_service.list_users", return_value=[]):
            approved = self.service.approve_event("e-review", "coord-1")

        self.assertEqual(approved.status, "planning")

    def test_approve_event_conflicts_when_it_is_a_draft(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_event(created.eventId, "coord-1")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.get_event(created.eventId).status, "draft")

    def test_reject_event_stores_the_reason_and_explanation(self):
        insert_event(self.db, eventId="e-reject", status="under review", coordinatorId="coord-1")

        rejected, *_ = self.reject("e-reject", data=rejection("insufficient notice", "Too close to the date."))
        log = self.service.get_activity_log("e-reject")
        decision = self.service.get_event_decision("e-reject", {"userId": "coord-1", "role": "coordinator"})

        self.assertEqual(rejected.status, "rejected")
        self.assertEqual((rejected.decisionReason, rejected.decisionNote), ("insufficient notice", "Too close to the date."))
        self.assertEqual((rejected.decidedBy, rejected.decision), ("coord-1", "rejected"))
        self.assertEqual(
            (decision.decision, decision.decisionReason, decision.decisionNote, decision.decidedBy),
            ("rejected", "insufficient notice", "Too close to the date.", "coord-1"),
        )
        self.assertEqual((log[-1].toStatus, log[-1].changedBy), ("rejected", "coord-1"))

    def test_the_activity_log_carries_the_listed_reason_but_not_the_explanation(self):
        insert_event(self.db, eventId="e-log", status="under review", coordinatorId="coord-1")

        self.reject("e-log", data=rejection("insufficient equipment", "The LED wall is booked."))
        log = self.service.get_activity_log("e-log")

        self.assertEqual(log[-1].note, "insufficient equipment")
        self.assertNotIn("LED wall", str(log[-1]))

    def test_a_request_with_changes_requested_can_be_rejected(self):
        insert_event(self.db, eventId="e-changes", status="changes requested", coordinatorId="coord-1")

        rejected, *_ = self.reject("e-changes")

        self.assertEqual(rejected.status, "rejected")

    def test_rejecting_releases_venue_bookings_and_equipment(self):
        insert_event(self.db, eventId="e-held", status="under review", coordinatorId="coord-1")

        _, venues, equipment, _ = self.reject("e-held")

        venues.assert_called_once_with("e-held", "Bearer token")
        equipment.assert_called_once_with("e-held", "Bearer token")

    def test_rejecting_emails_the_organiser_the_reason_and_explanation(self):
        insert_event(self.db, eventId="e-mail", status="under review", coordinatorId="coord-1", eventName="Gala")
        directory = [{"userId": "org-1", "userName": "Amy", "email": "amy@example.com", "role": "organiser"}]

        _, _, _, sent = self.reject("e-mail", directory=directory)

        to, subject, body, _ = sent.call_args.args
        self.assertEqual((to, subject), ("amy@example.com", "Gala was rejected"))
        self.assertIn("no suitable venue available", body)
        self.assertIn("No hall fits those dates.", body)

    def test_rejecting_publishes_a_notification_to_the_organiser_only(self):
        insert_event(self.db, eventId="e-note", status="under review", coordinatorId="coord-1", eventName="Gala")

        self.reject("e-note", data=rejection("insufficient notice", "Too close to the date."))

        args, kwargs = self.published.call_args
        self.assertEqual(args[:3], ("event.rejected", "e-note", "e-note:event.rejected"))
        self.assertEqual(args[3], [{"userId": "org-1", "role": "organiser"}])
        self.assertEqual(
            args[4], {"eventName": "Gala", "reason": "insufficient notice", "explanation": "Too close to the date."}
        )
        self.assertEqual(kwargs["actor_id"], "coord-1")

    def test_the_rejection_stands_when_the_organiser_cannot_be_found(self):
        insert_event(self.db, eventId="e-nobody", status="under review", coordinatorId="coord-1")

        rejected, _, _, sent = self.reject("e-nobody", directory=[])

        self.assertEqual(rejected.status, "rejected")
        sent.assert_not_called()

    def test_a_rejected_request_cannot_be_rejected_again_or_approved(self):
        insert_event(self.db, eventId="e-final", status="under review", coordinatorId="coord-1")
        self.reject("e-final")

        with self.assertRaises(HTTPException) as again:
            self.reject("e-final")
        with self.assertRaises(HTTPException) as approve:
            self.service.approve_event("e-final", "coord-1")

        self.assertEqual((again.exception.status_code, approve.exception.status_code), (409, 409))
        self.assertEqual(self.service.get_event("e-final").status, "rejected")

    def test_a_missing_reason_or_explanation_is_refused(self):
        with self.assertRaises(ValidationError):
            EventRejection(explanation="Because")
        with self.assertRaises(ValidationError):
            EventRejection(reason="no suitable venue available")
        with self.assertRaises(ValidationError):
            EventRejection(reason="no suitable venue available", explanation="   ")

    def test_a_reason_outside_the_list_is_refused(self):
        with self.assertRaises(ValidationError):
            EventRejection(reason="Dates clash", explanation="Because")

    def test_reject_conflicts_once_the_request_has_been_decided(self):
        insert_event(self.db, eventId="e-planning", status="planning", coordinatorId="coord-1")

        with self.assertRaises(HTTPException) as ctx:
            self.reject("e-planning")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("this one is planning", ctx.exception.detail)

    def test_only_the_assigned_coordinator_can_reject(self):
        insert_event(self.db, eventId="e-theirs", status="under review", coordinatorId="coord-2")
        created = self.service.create_event(event_create(), "org-1", "o1")

        for event_id, expected in (("e-theirs", 403), (created.eventId, 409)):
            with self.assertRaises(HTTPException) as ctx:
                self.reject(event_id)
            self.assertEqual(ctx.exception.status_code, expected, event_id)
        self.assertEqual(self.service.get_event("e-theirs").status, "under review")

    def test_reject_event_conflicts_when_it_is_a_draft(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.reject(created.eventId)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.get_event(created.eventId).status, "draft")

    def test_complete_event_moves_a_confirmed_past_event_to_completed(self):
        event = insert_event(
            self.db,
            eventId="e-done",
            status="confirmed",
            coordinatorId="coord-1",
            proposedEndAt=datetime.utcnow() - timedelta(days=1),
        )

        completed = self.service.complete_event(event.eventId, "coord-1")
        log = self.service.get_activity_log(event.eventId)

        self.assertEqual(completed.status, "completed")
        self.assertEqual(log[-1].toStatus, "completed")
        self.assertEqual(log[-1].changedBy, "coord-1")

    def test_complete_event_is_404_when_the_event_is_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.complete_event("missing", "coord-1")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_complete_event_is_403_for_a_coordinator_who_is_not_assigned(self):
        event = insert_event(
            self.db,
            eventId="e-done",
            status="confirmed",
            coordinatorId="coord-1",
            proposedEndAt=datetime.utcnow() - timedelta(days=1),
        )

        with self.assertRaises(HTTPException) as ctx:
            self.service.complete_event(event.eventId, "coord-2")

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.service.get_event(event.eventId).status, "confirmed")

    def test_complete_event_conflicts_when_it_is_not_confirmed(self):
        event = insert_event(
            self.db,
            eventId="e-done",
            status="submitted",
            coordinatorId="coord-1",
            proposedEndAt=datetime.utcnow() - timedelta(days=1),
        )

        with self.assertRaises(HTTPException) as ctx:
            self.service.complete_event(event.eventId, "coord-1")

        self.assertEqual(ctx.exception.status_code, 409)

    def test_complete_event_conflicts_before_the_end_time_has_passed(self):
        event = insert_event(
            self.db,
            eventId="e-done",
            status="confirmed",
            coordinatorId="coord-1",
            proposedEndAt=datetime.utcnow() + timedelta(days=1),
        )

        with self.assertRaises(HTTPException) as ctx:
            self.service.complete_event(event.eventId, "coord-1")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.get_event(event.eventId).status, "confirmed")

    def test_complete_is_allowed_at_the_end_instant_and_refused_one_microsecond_before(self):
        now = datetime(2026, 10, 3, 18, 0)
        on_time = insert_event(
            self.db,
            eventId="e-on-time",
            status="confirmed",
            coordinatorId="coord-1",
            proposedEndAt=now,
        )
        still_running = insert_event(
            self.db,
            eventId="e-running",
            status="confirmed",
            coordinatorId="coord-1",
            proposedEndAt=now + timedelta(microseconds=1),
        )

        with patch("app.services.event_service.datetime") as clock:
            clock.utcnow.return_value = now
            completed = self.service.complete_event(on_time.eventId, "coord-1")
            with self.assertRaises(HTTPException) as ctx:
                self.service.complete_event(still_running.eventId, "coord-1")

        self.assertEqual(completed.status, "completed")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.get_event(still_running.eventId).status, "confirmed")
