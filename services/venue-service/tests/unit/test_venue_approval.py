"""SPM-8: approve a venue booking request."""

from datetime import datetime, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_booking import VenueBooking
from app.models.venue_unavailability import VenueUnavailability
from app.schemas.venue import OperatingHours
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, COORDINATOR, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

MONDAY = datetime(2030, 1, 7)
ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def at(hour, minute=0):
    return MONDAY + timedelta(hours=hour, minutes=minute)


class ApprovalCase(VenueCase):
    """Harbour Hall: open every day, 30 minutes setup and 45 minutes turnaround, so
    event A (10:00 to 12:00) occupies it from 09:30 to 12:45."""

    def setUp(self):
        super().setUp()
        self.hall = self.service.create_venue(
            venue_create(
                name="Harbour Hall",
                setupMinutes=30,
                turnaroundMinutes=45,
                operatingHours=[OperatingHours(day=d, opens="00:00", closes="24:00") for d in ALL_DAYS],
            ),
            CALLER,
        )

    def request(self, event_id, starts_at, ends_at):
        return self.service.create_booking(
            booking_create(
                self.hall.venueId,
                eventId=event_id,
                startsAt=starts_at,
                endsAt=ends_at,
                requirementsSnapshot="Theatre for 120, stage, wheelchair access",
            ),
            "u-coord",
            event_snapshot={
                "eventName": f"Event {event_id}",
                "clientOrganisation": "Acme Pte Ltd",
                "startsAt": starts_at.isoformat(),
                "endsAt": ends_at.isoformat(),
                "expectedAttendance": 120,
                "layout": "Theatre",
                "accessibilityNeeds": "Wheelchair access",
                "requiredFacilities": "Stage",
            },
        ).bookingId

    def approve(self, booking_id, name="Vinod Kumar"):
        return self.service.approve_booking(booking_id, "u-venue", None, name)

    def refused(self, call, status=409):
        with self.assertRaises(HTTPException) as ctx:
            call()
        self.assertEqual(ctx.exception.status_code, status)
        return ctx.exception.detail

    def free(self, starts_at, ends_at):
        rows = self.service.search_venues(starts_at=starts_at, ends_at=ends_at, exclude_event_id="e-other")
        return self.hall.venueId in [row.venueId for row in rows]


class TestViewingARequest(ApprovalCase):
    """AC1: event timing, venue requirements, and submission time."""

    def test_a_submitted_request_shows_its_timing_requirements_and_submission_time(self):
        before = datetime.utcnow()
        booking = self.service.get_booking(self.request("e-a", at(10), at(12)))

        self.assertEqual((booking.status, booking.venueName), ("pending", "Harbour Hall"))
        self.assertEqual((booking.startsAt, booking.endsAt), (at(10), at(12)))
        self.assertEqual((booking.setupStartsAt, booking.teardownEndsAt), (at(9, 30), at(12, 45)))
        self.assertEqual(booking.requirementsSnapshot, "Theatre for 120, stage, wheelchair access")
        self.assertEqual(
            {k: booking.eventSnapshot[k] for k in ("eventName", "expectedAttendance", "layout", "requiredFacilities", "accessibilityNeeds")},
            {
                "eventName": "Event e-a",
                "expectedAttendance": 120,
                "layout": "Theatre",
                "requiredFacilities": "Stage",
                "accessibilityNeeds": "Wheelchair access",
            },
        )
        self.assertGreaterEqual(booking.createdAt, before)

    def test_it_waits_in_the_pending_queue(self):
        a = self.request("e-a", at(10), at(12))

        self.assertEqual([row.bookingId for row in self.service.list_bookings("pending", None, None)], [a])


class TestApproving(ApprovalCase):
    """AC2 and AC10: approval confirms the booking, links venue and event, and locks the window."""

    def test_a_pending_request_is_approved_into_a_confirmed_booking(self):
        approved = self.approve(self.request("e-a", at(10), at(12)))

        self.assertEqual(
            (approved.status, approved.venueId, approved.eventId), ("approved", self.hall.venueId, "e-a")
        )

    def test_a_request_under_its_own_active_hold_can_be_approved(self):
        a = self.request("e-a", at(10), at(12))
        self.service.place_hold(a, at(8) - timedelta(days=1), CALLER)

        approved = self.approve(a)

        self.assertEqual((approved.status, approved.hold.state), ("approved", "approved"))

    def test_the_venue_is_then_locked_for_the_occupied_window(self):
        self.approve(self.request("e-a", at(10), at(12)))
        b = self.request("e-b", at(12), at(13))  # set up from 11:30, inside A's 09:30 to 12:45

        self.assertIn("Harbour Hall is already confirmed for", self.refused(lambda: self.approve(b)))
        self.assertFalse(self.free(at(12), at(13)))
        self.assertTrue(self.free(at(13, 15), at(14)))  # set up from 12:45: only touches


class TestAnApprovedBookingCanBeViewed(ApprovalCase):
    """AC3: the booking can be viewed and reserves the occupied window."""

    def test_the_booking_shows_as_approved_with_its_occupied_window(self):
        a = self.request("e-a", at(10), at(12))
        self.approve(a)

        booking = self.service.get_booking(a)

        self.assertEqual((booking.status, booking.setupStartsAt, booking.teardownEndsAt), ("approved", at(9, 30), at(12, 45)))
        self.assertEqual([row.bookingId for row in self.service.list_bookings("approved", None, self.hall.venueId)], [a])
        self.assertEqual(self.service.list_bookings("pending", None, self.hall.venueId), [])


class TestAnApprovedBookingStaysLocked(ApprovalCase):
    """AC4: nothing can approve, reject, withdraw, or hold it again, and it keeps the venue."""

    def setUp(self):
        super().setUp()
        self.a = self.request("e-a", at(10), at(12))
        self.approve(self.a)

    def test_it_cannot_be_approved_or_rejected_again(self):
        self.assertEqual(self.refused(lambda: self.approve(self.a)), "Booking is already approved")
        self.assertEqual(
            self.refused(lambda: self.service.reject_booking(self.a, "u-venue", "No")), "Booking is already approved"
        )

    def test_it_cannot_be_withdrawn_or_held(self):
        self.assertIn(
            "Only a pending request can be withdrawn",
            self.refused(lambda: self.service.withdraw_booking(self.a, COORDINATOR, COORDINATOR["userId"])),
        )
        self.assertIn(
            "Only a pending booking request can be held",
            self.refused(lambda: self.service.place_hold(self.a, at(8), CALLER)),
        )

    def test_it_stays_approved_and_keeps_the_venue(self):
        self.db.expire_all()

        self.assertEqual(self.service.get_booking(self.a).status, "approved")
        self.assertFalse(self.free(at(10), at(12)))


class TestTheApprovalRecord(ApprovalCase):
    """AC5: who approved it and when, kept with the booking."""

    def test_the_approver_and_the_time_are_recorded_and_kept(self):
        a = self.request("e-a", at(10), at(12))
        before = datetime.utcnow()
        self.approve(a, name="Vinod Kumar")
        after = datetime.utcnow()
        self.db.expire_all()

        stored = self.db.get(VenueBooking, a)
        self.assertEqual((stored.reviewedBy, stored.reviewedByName), ("u-venue", "Vinod Kumar"))
        self.assertTrue(before <= stored.reviewedAt <= after)
        shown = self.service.get_booking(a)
        self.assertEqual((shown.reviewedBy, shown.reviewedByName, shown.reviewedAt), ("u-venue", "Vinod Kumar", stored.reviewedAt))

    def test_the_record_stays_when_the_booking_is_later_released(self):
        a = self.request("e-a", at(10), at(12))
        approved = self.approve(a)

        self.service.release_event_bookings("e-a")  # SPM-114: the event is cancelled afterwards
        self.db.expire_all()

        stored = self.service.get_booking(a)
        self.assertEqual(stored.status, "cancelled")
        self.assertEqual(
            (stored.reviewedBy, stored.reviewedByName, stored.reviewedAt),
            ("u-venue", "Vinod Kumar", approved.reviewedAt),
        )

    def test_a_refused_approval_records_nobody(self):
        self.approve(self.request("e-a", at(10), at(12)))
        b = self.request("e-b", at(12), at(13))
        self.refused(lambda: self.approve(b))

        stored = self.db.get(VenueBooking, b)
        self.assertEqual((stored.status, stored.reviewedBy, stored.reviewedByName, stored.reviewedAt), ("pending", None, None, None))


class TestApprovalIsBlocked(ApprovalCase):
    """AC6 to AC8: an overlap blocks approval, says why, and leaves the request pending."""

    def setUp(self):
        super().setUp()
        self.a = self.request("e-a", at(10), at(12))  # occupies 09:30 to 12:45

    def assert_still_pending(self, booking_id):
        self.db.expire_all()
        self.assertEqual(self.service.get_booking(booking_id).status, "pending")

    def block(self, starts_at, ends_at):
        self.db.add(
            VenueUnavailability(
                unavailabilityId=f"u-{starts_at:%H%M}",
                venueId=self.hall.venueId,
                startsAt=starts_at,
                endsAt=ends_at,
                reason="maintenance",
                createdBy="u-venue",
            )
        )
        self.db.commit()

    def test_unavailability_overlapping_the_occupied_window(self):
        self.block(at(9), at(9, 45))  # inside the setup only

        detail = self.refused(lambda: self.approve(self.a))

        self.assertEqual(
            detail,
            "Harbour Hall is unavailable from 07 Jan 2030, 09:00 AM to 09:45 AM UTC (maintenance), "
            "so this request cannot be approved.",
        )
        self.assert_still_pending(self.a)

    def test_unavailability_that_only_touches_the_window_does_not_block(self):
        self.block(at(12, 45), at(13, 30))  # starts as the turnaround ends

        self.assertEqual(self.approve(self.a).status, "approved")

    def test_a_confirmed_booking_overlapping_the_occupied_window(self):
        other = self.request("e-b", at(7), at(9))  # turned around until 09:45, inside A's setup
        self.approve(other)

        detail = self.refused(lambda: self.approve(self.a))

        self.assertTrue(detail.startswith('Harbour Hall is already confirmed for "Event e-b" at an overlapping time'))
        self.assert_still_pending(self.a)

    def test_an_active_hold_overlapping_the_occupied_window(self):
        held = self.request("e-b", at(12), at(13))
        self.service.place_hold(held, at(8, 0) - timedelta(days=1), CALLER)

        detail = self.refused(lambda: self.approve(self.a))

        self.assertIn('Harbour Hall is on a tentative hold until 06 Jan 2030, 08:00 AM UTC for "Event e-b"', detail)
        self.assert_still_pending(self.a)


class TestAnExpiredHold(ApprovalCase):
    """AC9: an expired hold does not block approval and is not a confirmed booking."""

    def test_it_does_not_block_and_stays_only_a_request(self):
        held = self.request("e-b", at(12), at(13))
        self.service.place_hold(held, at(8) - timedelta(days=1), CALLER)
        row = self.db.get(VenueBooking, held)
        row.holdExpiresAt = datetime.utcnow() - timedelta(minutes=1)
        self.db.commit()
        a = self.request("e-a", at(10), at(12))

        self.assertEqual(self.approve(a).status, "approved")
        expired = self.service.get_booking(held)
        self.assertEqual((expired.status, expired.hold.state), ("pending", "expired"))
        self.assertNotIn(held, [row.bookingId for row in self.service.list_bookings("approved", None, None)])


class TestCompetingRequests(ApprovalCase):
    """AC11: requests competing for the same venue and time are listed oldest first."""

    def test_competing_requests_are_listed_by_submission_time_oldest_first(self):
        first, second, third = (self.request(e, at(10), at(12)) for e in ("e-x", "e-y", "e-z"))
        elsewhere = self.service.create_venue(venue_create(code="MH-B", name="Marina Hall B"), CALLER)
        other = self.service.create_booking(
            booking_create(elsewhere.venueId, eventId="e-w", startsAt=at(10), endsAt=at(12)), "u-coord"
        ).bookingId
        # Submission times out of creation order, so the order must come from createdAt.
        for booking_id, minutes in ((first, 30), (second, 10), (third, 20), (other, 5)):
            self.db.get(VenueBooking, booking_id).createdAt = datetime(2029, 12, 1, 9, minutes)
        self.db.commit()

        listed = [row.bookingId for row in self.service.list_bookings("pending", None, self.hall.venueId)]

        self.assertEqual(listed, [second, third, first])

    def test_once_the_oldest_is_approved_the_others_are_refused(self):
        older, newer = self.request("e-x", at(10), at(12)), self.request("e-y", at(11), at(13))

        self.approve(older)

        self.assertIn("is already confirmed for", self.refused(lambda: self.approve(newer)))


class TestApprovalRoute(ApprovalCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_the_approver_is_recorded_by_name_from_their_account(self):
        a = self.request("e-a", at(10), at(12))

        with signed_in_as("venue"):
            approved = self.client.post(f"/venues/bookings/{a}/approve", headers=HEADERS, json={})

        self.assertEqual(approved.status_code, 200)
        self.assertEqual(
            (approved.json()["status"], approved.json()["reviewedBy"], approved.json()["reviewedByName"]),
            ("approved", "u-venue", "venue"),
        )

    def test_only_venue_staff_can_approve(self):
        a = self.request("e-a", at(10), at(12))
        for role in ("coordinator", "organiser", "techsupport", "safety", "attendee"):
            with self.subTest(role=role), signed_in_as(role):
                self.assertEqual(
                    self.client.post(f"/venues/bookings/{a}/approve", headers=HEADERS, json={}).status_code, 403
                )
        self.assertEqual(self.service.get_booking(a).status, "pending")
