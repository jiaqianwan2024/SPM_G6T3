from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_booking import VenueBooking
from app.services.venue_service import DASHBOARD_UPCOMING_DAYS
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, COORDINATOR, VenueCase, booking_create, venue_create

NOW = datetime(2030, 1, 7, 2, 0)  # Monday 10:00 Singapore time
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


class DashboardCase(VenueCase):
    """SPM-57: Venue Staff's home screen. Two venues; each booking is its own event."""

    def setUp(self):
        super().setUp()
        self.hall = self.service.create_venue(venue_create(), CALLER)
        self.room = self.service.create_venue(venue_create(code="RR-1", name="Riverside Room"), CALLER)

    def booking(self, event_id, starts_at, hours=2, venue=None, status="pending", created_at=None, name=None):
        venue = venue or self.hall
        row = self.service.create_booking(
            booking_create(venue.venueId, eventId=event_id, startsAt=starts_at, endsAt=starts_at + hours * HOUR),
            "u-coord",
            event_snapshot={"eventName": name or f"Event {event_id}"},
        )
        if status == "approved":
            self.service.approve_booking(row.bookingId, "u-venue", None)
        elif status == "rejected":
            self.service.reject_booking(row.bookingId, "u-venue", "Not suitable")
        if created_at:
            stored = self.db.get(VenueBooking, row.bookingId)
            stored.createdAt = created_at
            self.db.commit()
        return row

    def flag(self, booking, note="The event moved by a day."):
        stored = self.db.get(VenueBooking, booking.bookingId)
        stored.needsReverification = True
        stored.reverificationNote = note
        self.db.commit()

    def board(self):
        return self.service.venue_dashboard(NOW)

    @staticmethod
    def ids(rows):
        return [row.bookingId for row in rows]


class TestPendingRequests(DashboardCase):
    """AC1: requests awaiting a decision, with the event, requested venue, and requested date and time."""

    def test_pending_requests_are_listed_oldest_first_with_event_venue_and_times(self):
        later = self.booking("e-later", NOW + 5 * DAY, created_at=NOW - HOUR, name="Board Meeting")
        older = self.booking("e-older", NOW + 9 * DAY, venue=self.room, created_at=NOW - DAY, name="AI Summit")

        pending = self.board().pending

        self.assertEqual(self.ids(pending), [older.bookingId, later.bookingId])
        first = pending[0]
        self.assertEqual(
            (first.eventSnapshot["eventName"], first.venueName, first.startsAt, first.endsAt),
            ("AI Summit", "Riverside Room", NOW + 9 * DAY, NOW + 9 * DAY + 2 * HOUR),
        )

    def test_decided_requests_are_not_pending(self):
        self.booking("e-approved", NOW + 2 * DAY, status="approved")
        self.booking("e-rejected", NOW + 3 * DAY, status="rejected")

        self.assertEqual(self.board().pending, [])


class TestReverification(DashboardCase):
    """AC2: confirmed bookings flagged after a significant change to their event."""

    def test_flagged_bookings_are_listed_soonest_first_with_what_changed(self):
        later = self.booking("e-later", NOW + 6 * DAY, status="approved")
        sooner = self.booking("e-sooner", NOW + 2 * DAY, venue=self.room, status="approved")
        self.booking("e-unflagged", NOW + 4 * DAY, status="approved")
        self.flag(later)
        self.flag(sooner, "Expected attendance rose to 300.")

        flagged = self.board().reverification

        self.assertEqual(self.ids(flagged), [sooner.bookingId, later.bookingId])
        self.assertEqual(flagged[0].reverificationNote, "Expected attendance rose to 300.")

    def test_a_flag_on_an_event_that_has_ended_is_left_out(self):
        # Boundary: an event that ended at this moment has nothing left to prepare.
        ended = self.booking("e-ended", NOW - 2 * HOUR, status="approved")
        running = self.booking("e-running", NOW - HOUR, status="approved", venue=self.room)
        self.flag(ended)
        self.flag(running)

        self.assertEqual(self.ids(self.board().reverification), [running.bookingId])


class TestUpcoming(DashboardCase):
    """AC3: confirmed bookings in the next few days, so the day's preparation is visible."""

    def test_confirmed_bookings_in_the_window_are_listed_soonest_first(self):
        later = self.booking("e-later", NOW + 3 * DAY, status="approved")
        today = self.booking("e-today", NOW + 4 * HOUR, venue=self.room, status="approved")
        self.booking("e-pending", NOW + DAY, status="pending")

        self.assertEqual(self.ids(self.board().upcoming), [today.bookingId, later.bookingId])

    def test_the_window_ends_exactly_the_set_number_of_days_ahead(self):
        self.assertEqual(DASHBOARD_UPCOMING_DAYS, 7)
        edge = self.booking("e-edge", NOW + 7 * DAY, status="approved")
        self.booking("e-past-edge", NOW + 7 * DAY + timedelta(minutes=1), venue=self.room, status="approved")

        self.assertEqual(self.ids(self.board().upcoming), [edge.bookingId])

    def test_an_event_under_way_is_shown_and_one_that_ended_is_not(self):
        running = self.booking("e-running", NOW - HOUR, status="approved")
        self.booking("e-ended", NOW - 3 * HOUR, venue=self.room, status="approved")

        self.assertEqual(self.ids(self.board().upcoming), [running.bookingId])
        self.assertEqual(self.board().upcomingDays, DASHBOARD_UPCOMING_DAYS)


class TestEmpty(DashboardCase):
    """AC6: with nothing to show, every list is empty (the screen shows each section's empty state)."""

    def test_no_bookings_gives_three_empty_lists(self):
        board = self.board()

        self.assertEqual((board.pending, board.reverification, board.upcoming), ([], [], []))

    def test_now_defaults_to_the_current_time(self):
        self.booking("e-soon", datetime.utcnow() + DAY, status="approved")

        self.assertEqual(len(self.service.venue_dashboard().upcoming), 1)


class TestDashboardRoute(VenueCase):
    """AC5: the same access as the Booking Requests screen, which is Venue Staff only."""

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_venue_staff_get_the_dashboard(self):
        with patch("app.routers.venue.resolve_caller", return_value=CALLER) as caller:
            response = self.client.get("/venues/dashboard", headers={"Authorization": "Bearer token"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"pending", "reverification", "upcoming", "upcomingDays"})
        self.assertEqual(caller.call_args.kwargs["allowed_roles"], {"venue"})

    def test_every_other_role_is_refused(self):
        from shared.exceptions.http import forbidden

        refused = forbidden("You do not have permission to perform this action")
        for role in (COORDINATOR, {"role": "organiser"}, {"role": "attendee"}, {"role": "techsupport"}):
            with self.subTest(role=role["role"]), patch("app.routers.venue.resolve_caller", side_effect=refused):
                response = self.client.get("/venues/dashboard", headers={"Authorization": "Bearer token"})
                self.assertEqual(response.status_code, 403)
