from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

from app.schemas.event import EventAssignmentCreate
from tests.unit.support import EventCase, draft_payload, event_create, insert_event


class TestEventDecisions(EventCase):
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

    def test_reject_event_stores_the_reason(self):
        insert_event(self.db, eventId="e-reject", status="under review", coordinatorId="coord-1")

        rejected = self.service.reject_event("e-reject", "coord-1", "Dates clash")
        log = self.service.get_activity_log("e-reject")

        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(log[-1].note, "Dates clash")
        self.assertEqual(log[-1].changedBy, "coord-1")

    def test_reject_conflicts_once_the_request_has_been_decided(self):
        insert_event(self.db, eventId="e-planning", status="planning", coordinatorId="coord-1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.reject_event("e-planning", "coord-1", "Too late")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("already planning", ctx.exception.detail)

    def test_only_the_assigned_coordinator_can_reject(self):
        insert_event(self.db, eventId="e-theirs", status="under review", coordinatorId="coord-2")
        created = self.service.create_event(event_create(), "org-1", "o1")

        for event_id, expected in (("e-theirs", 403), (created.eventId, 409)):
            with self.assertRaises(HTTPException) as ctx:
                self.service.reject_event(event_id, "coord-1", "Dates clash")
            self.assertEqual(ctx.exception.status_code, expected, event_id)
        self.assertEqual(self.service.get_event("e-theirs").status, "under review")

    def test_reject_event_conflicts_when_it_is_a_draft(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.reject_event(created.eventId, "coord-1", "Dates clash")

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
