import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.venue import EventFacts, OperatingHours
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EVENT = EventFacts(
    eventName="AI Summit",
    status="planning",
    coordinatorId="u-coordinator",
    organisationId="org-1",
    organisationName="Apex Partners",
    expectedAttendance=10,
    layoutPreference="Theatre",
    proposedStartAt=datetime(2030, 1, 7, 10),
    proposedEndAt=datetime(2030, 1, 7, 12),
)


class TestReplacementRoutes(VenueCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        hours = [OperatingHours(day=d, opens="08:00", closes="18:00") for d in ALL_DAYS]
        self.venue_id = self.service.create_venue(venue_create(operatingHours=hours), CALLER).venueId
        self.other_id = self.service.create_venue(
            venue_create(name="Exhibition Hall B", code="EH-B", operatingHours=hours), CALLER
        ).venueId
        self.patches = {
            "event": patch("app.routers.venue.fetch_event_facts", return_value=EVENT),
            "notify": patch("app.routers.venue.notify_venue_staff", return_value=2),
            "coordinator": patch("app.routers.venue.notify_coordinator", return_value=True),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def call(self, role, method, path, body=None):
        with signed_in_as(role):
            return self.client.request(method, path, headers=HEADERS, json=body)

    def affected_booking(self):
        with signed_in_as("coordinator"):
            created = self.client.post(
                "/venues/bookings",
                headers=HEADERS,
                json={
                    "venueId": self.venue_id,
                    "eventId": "e1",
                    "startsAt": "2030-01-07T10:00:00Z",
                    "endsAt": "2030-01-07T12:00:00Z",
                },
            )
        self.assertEqual(created.status_code, 201, created.text)
        booking_id = created.json()["bookingId"]
        approved = self.service.approve_booking(booking_id, CALLER["userId"], None)
        blocked = self.call(
            "venue",
            "POST",
            f"/venues/{self.venue_id}/unavailability",
            {
                "startsAt": "2030-01-07T10:00:00Z",
                "endsAt": "2030-01-07T12:00:00Z",
                "reason": "maintenance",
                "acknowledgeConflicts": True,
            },
        )
        self.assertEqual(blocked.status_code, 201, blocked.text)
        return approved.bookingId

    def test_recording_a_block_does_not_read_the_event_and_a_coordinator_cannot_record_one(self):
        self.mocks["event"].reset_mock()
        saved = self.call(
            "venue",
            "POST",
            f"/venues/{self.venue_id}/unavailability",
            {"startsAt": "2030-01-07T10:00:00Z", "endsAt": "2030-01-07T12:00:00Z", "reason": "maintenance"},
        )

        self.assertEqual(saved.status_code, 201, saved.text)
        self.mocks["event"].assert_not_called()
        refused = self.call(
            "coordinator",
            "POST",
            f"/venues/{self.venue_id}/unavailability",
            {"startsAt": "2030-01-07T10:00:00Z", "endsAt": "2030-01-07T12:00:00Z", "reason": "maintenance"},
        )
        self.assertEqual(refused.status_code, 403)

    def test_the_assigned_coordinator_can_request_a_replacement_and_staff_are_told(self):
        booking_id = self.affected_booking()
        self.mocks["notify"].reset_mock()
        self.mocks["event"].reset_mock()

        created = self.call(
            "coordinator",
            "POST",
            f"/venues/bookings/{booking_id}/replacement",
            {"venueId": self.other_id},
        )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["status"], "pending")
        self.assertEqual(created.json()["venueId"], self.other_id)
        self.mocks["event"].assert_called_once()
        self.assertEqual(self.mocks["notify"].call_count, 2)
        original = self.call("coordinator", "GET", f"/venues/bookings/{booking_id}")
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.json()["status"], "cancelled")
        refused = self.call("venue", "POST", f"/venues/bookings/{booking_id}/replacement", {"venueId": self.other_id})
        self.assertEqual(refused.status_code, 403)

    def test_staff_can_change_and_remove_a_block_and_the_coordinator_is_told(self):
        booking_id = self.affected_booking()
        self.mocks["event"].reset_mock()
        self.mocks["coordinator"].reset_mock()
        listed = self.call("venue", "GET", f"/venues/{self.venue_id}/unavailability")
        self.assertEqual(listed.status_code, 200, listed.text)
        block_id = listed.json()[0]["unavailabilityId"]

        updated = self.call(
            "venue", "PATCH", f"/venues/{self.venue_id}/unavailability/{block_id}", {"note": "updated note"}
        )
        self.assertEqual((updated.status_code, updated.json()["note"]), (200, "updated note"))
        self.mocks["coordinator"].assert_not_called()
        kept = self.call("coordinator", "GET", f"/venues/bookings/{booking_id}")
        self.assertEqual(kept.json()["status"], "approved")

        moved = self.call(
            "venue",
            "PATCH",
            f"/venues/{self.venue_id}/unavailability/{block_id}",
            {"startsAt": "2030-01-07T09:00:00Z", "endsAt": "2030-01-07T11:00:00Z"},
        )
        self.assertEqual(moved.status_code, 409, moved.text)
        self.assertIn("e1", moved.text)
        self.mocks["coordinator"].reset_mock()
        moved = self.call(
            "venue",
            "PATCH",
            f"/venues/{self.venue_id}/unavailability/{block_id}",
            {
                "startsAt": "2030-01-07T09:00:00Z",
                "endsAt": "2030-01-07T11:00:00Z",
                "acknowledgeConflicts": True,
            },
        )
        self.assertEqual(moved.status_code, 200, moved.text)
        self.mocks["coordinator"].assert_called_once()
        self.assertEqual(self.mocks["coordinator"].call_args.args[5], "venue.unavailability")
        self.assertIn("unavailable", self.mocks["coordinator"].call_args.args[3])

        removed = self.call("venue", "DELETE", f"/venues/{self.venue_id}/unavailability/{block_id}")
        self.assertEqual(removed.status_code, 204, removed.text)
        self.assertEqual(self.call("venue", "GET", f"/venues/{self.venue_id}/unavailability").json(), [])
        actions = " ".join(row["action"] for row in self.call("venue", "GET", f"/venues/{self.venue_id}/activity-log").json())
        self.assertIn("unavailability created", actions)
        self.assertIn("unavailability updated", actions)
        self.assertIn("unavailability cancelled", actions)
        self.assertEqual(
            self.call("coordinator", "DELETE", f"/venues/{self.venue_id}/unavailability/{block_id}").status_code, 403
        )

    def test_a_notification_failure_still_leaves_the_block_saved(self):
        with signed_in_as("coordinator"):
            created = self.client.post(
                "/venues/bookings",
                headers=HEADERS,
                json={
                    "venueId": self.venue_id,
                    "eventId": "e1",
                    "startsAt": "2030-01-08T10:00:00Z",
                    "endsAt": "2030-01-08T12:00:00Z",
                },
            )
        self.assertEqual(created.status_code, 201, created.text)
        self.service.approve_booking(created.json()["bookingId"], CALLER["userId"], None)
        self.mocks["coordinator"].reset_mock()
        self.mocks["event"].side_effect = RuntimeError("event service down")
        try:
            saved = self.call(
                "venue",
                "POST",
                f"/venues/{self.venue_id}/unavailability",
                {
                    "startsAt": "2030-01-08T10:00:00Z",
                    "endsAt": "2030-01-08T12:00:00Z",
                    "reason": "safety issue",
                    "acknowledgeConflicts": True,
                },
            )
        finally:
            self.mocks["event"].side_effect = None
        self.assertEqual(saved.status_code, 201, saved.text)
        self.mocks["coordinator"].assert_not_called()

        with signed_in_as("coordinator"):
            other = self.client.post(
                "/venues/bookings",
                headers=HEADERS,
                json={
                    "venueId": self.other_id,
                    "eventId": "e1",
                    "startsAt": "2030-01-08T10:00:00Z",
                    "endsAt": "2030-01-08T12:00:00Z",
                },
            )
        self.assertEqual(other.status_code, 201, other.text)
        self.service.approve_booking(other.json()["bookingId"], CALLER["userId"], None)
        self.mocks["event"].return_value = EVENT.model_copy(update={"coordinatorId": None})
        try:
            saved = self.call(
                "venue",
                "POST",
                f"/venues/{self.other_id}/unavailability",
                {
                    "startsAt": "2030-01-08T10:00:00Z",
                    "endsAt": "2030-01-08T12:00:00Z",
                    "reason": "internal activity",
                    "acknowledgeConflicts": True,
                },
            )
        finally:
            self.mocks["event"].return_value = EVENT
        self.assertEqual(saved.status_code, 201, saved.text)
        self.mocks["coordinator"].assert_not_called()


if __name__ == "__main__":
    unittest.main()
