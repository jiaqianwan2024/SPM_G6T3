"""SPM-88 AC9: a cancellation's venue release names what each booking was, and can be undone."""

from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError

from app.main import app
from app.models.venue_booking import VenueBooking
from app.schemas.venue import EventFacts, OperatingHours, RestoredBooking
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, booking_create, venue_create

ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
HEADERS = {"Authorization": "Bearer token"}
EVENT = EventFacts(eventName="Summit", coordinatorId="u-coord", organisationId="org-1")
START = datetime(2030, 1, 7, 2)


class RestoreCase(VenueCase):
    def setUp(self):
        super().setUp()
        self.hall = self.service.create_venue(
            venue_create(operatingHours=[OperatingHours(day=d, opens="00:00", closes="24:00") for d in ALL_DAYS]),
            CALLER,
        ).venueId

    def booking(self, event_id="e1", day=0, **fields):
        starts = START + timedelta(days=day)
        booking_id = self.service.create_booking(
            booking_create(self.hall, eventId=event_id, startsAt=starts, endsAt=starts + timedelta(hours=2)),
            "u-coord",
        ).bookingId
        row = self.db.get(VenueBooking, booking_id)
        for name, value in fields.items():
            setattr(row, name, value)
        self.db.commit()
        return booking_id

    def row(self, booking_id):
        self.db.expire_all()
        return self.db.get(VenueBooking, booking_id)


class TestReleaseNamesWhatWasReleased(RestoreCase):
    def test_each_released_booking_says_whether_it_was_pending_or_approved(self):
        pending = self.booking(day=0)
        approved = self.booking(day=1, status="approved")

        released = self.service.release_event_bookings("e1")

        self.assertEqual({row.bookingId: (row.status, row.previousStatus) for row in released}, {
            pending: ("cancelled", "pending"),
            approved: ("cancelled", "approved"),
        })


class TestRestore(RestoreCase):
    def test_each_booking_gets_its_status_back(self):
        pending = self.booking(day=0)
        approved = self.booking(day=1, status="approved")
        released = self.service.release_event_bookings("e1")

        restored = self.service.restore_event_bookings(
            "e1", [RestoredBooking(bookingId=row.bookingId, status=row.previousStatus) for row in released]
        )

        self.assertEqual({row.bookingId for row in restored}, {pending, approved})
        self.assertEqual((self.row(pending).status, self.row(approved).status), ("pending", "approved"))

    def test_a_hold_the_release_ended_is_given_back_but_one_that_ended_otherwise_is_not(self):
        held = self.booking(day=0, holdExpiresAt=datetime(2030, 1, 1), holdPlacedBy="u-venue")
        released_earlier = self.booking(
            day=1, holdExpiresAt=datetime(2030, 1, 1), holdEndedAt=datetime(2026, 1, 1), holdEndReason="released"
        )
        self.service.release_event_bookings("e1")

        self.service.restore_event_bookings(
            "e1", [RestoredBooking(bookingId=held, status="pending"), RestoredBooking(bookingId=released_earlier, status="pending")]
        )

        self.assertEqual((self.row(held).holdEndedAt, self.row(held).holdEndReason), (None, None))
        self.assertEqual(self.row(released_earlier).holdEndReason, "released")

    def test_another_events_booking_a_live_one_or_an_unknown_one_is_left_alone(self):
        theirs = self.booking(event_id="e2", status="cancelled")
        live = self.booking(day=1, status="approved")

        restored = self.service.restore_event_bookings(
            "e1",
            [
                RestoredBooking(bookingId=theirs, status="approved"),
                RestoredBooking(bookingId=live, status="pending"),
                RestoredBooking(bookingId="missing", status="pending"),
            ],
        )

        self.assertEqual(restored, [])
        self.assertEqual((self.row(theirs).status, self.row(live).status), ("cancelled", "approved"))

    def test_a_venue_booked_in_the_meantime_is_a_conflict_and_nothing_is_given_back(self):
        booking = self.booking(status="approved")
        self.service.release_event_bookings("e1")

        with patch.object(self.db, "commit", side_effect=DBAPIError("UPDATE", {}, Exception("45000"))):
            with self.assertRaises(HTTPException) as ctx:
                self.service.restore_event_bookings("e1", [RestoredBooking(bookingId=booking, status="approved")])

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.row(booking).status, "cancelled")


class TestRestoreRoute(RestoreCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.event = patch("app.routers.venue.fetch_event_facts", return_value=EVENT)
        self.event.start()

    def tearDown(self):
        self.event.stop()
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, path, caller, body):
        with patch("app.routers.venue.resolve_caller", return_value=caller):
            return self.client.post(path, headers=HEADERS, json=body)

    def test_the_release_reply_and_the_restore_round_trip_for_the_events_coordinator(self):
        coordinator = {"userId": "u-coord", "role": "coordinator"}
        booking = self.booking(status="approved")

        released = self.post("/venues/bookings/release", coordinator, {"eventId": "e1"})
        self.assertEqual([(row["bookingId"], row["previousStatus"]) for row in released.json()], [(booking, "approved")])

        restored = self.post(
            "/venues/bookings/restore", coordinator, {"eventId": "e1", "bookings": [{"bookingId": booking, "status": "approved"}]}
        )

        self.assertEqual(restored.status_code, 200)
        self.assertEqual([row["status"] for row in restored.json()], ["approved"])

    def test_someone_who_could_not_release_cannot_restore_either(self):
        booking = self.booking(status="cancelled")

        response = self.post(
            "/venues/bookings/restore",
            {"userId": "u-other", "role": "coordinator"},
            {"eventId": "e1", "bookings": [{"bookingId": booking, "status": "approved"}]},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.row(booking).status, "cancelled")
