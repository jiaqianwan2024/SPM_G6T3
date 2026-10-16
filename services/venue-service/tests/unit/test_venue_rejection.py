"""SPM-10: reject a venue booking request."""

from datetime import datetime, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_booking import VenueBooking
from app.services.occupancy import hold_state
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, COORDINATOR, venue_create
from tests.unit.test_venue_approval import ApprovalCase, at
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as


class RejectionCase(ApprovalCase):
    """Harbour Hall (30 minutes setup, 45 turnaround, open every day) plus Riverside Room
    to suggest instead. Event A (10:00 to 12:00) occupies the hall from 09:30 to 12:45."""

    def setUp(self):
        super().setUp()
        self.room = self.service.create_venue(venue_create(code="RR-1", name="Riverside Room"), CALLER)

    def reject(self, booking_id, reason="The hall is closed for maintenance.", name="Vinod Kumar", suggested=None):
        return self.service.reject_booking(booking_id, "u-venue", reason, name, suggested)

    def stored(self, booking_id):
        self.db.expire_all()
        return self.db.get(VenueBooking, booking_id)

    def queue(self, status="pending"):
        return [row.bookingId for row in self.service.list_bookings(status, None, self.hall.venueId)]


class TestViewingTheFullRequest(RejectionCase):
    """AC1: everything the request carries is there to read before deciding."""

    def test_a_pending_request_shows_its_full_details(self):
        a = self.request("e-a", at(10), at(12))
        self.db.get(VenueBooking, a).coordinatorNotes = "Please keep the side doors open."
        self.db.commit()

        booking = self.service.get_booking(a)

        self.assertEqual(booking.status, "pending")
        self.assertEqual(
            {k: booking.eventSnapshot[k] for k in ("eventName", "clientOrganisation", "expectedAttendance", "layout")},
            {"eventName": "Event e-a", "clientOrganisation": "Acme Pte Ltd", "expectedAttendance": 120, "layout": "Theatre"},
        )
        self.assertEqual((booking.startsAt, booking.endsAt), (at(10), at(12)))
        self.assertEqual((booking.setupStartsAt, booking.teardownEndsAt), (at(9, 30), at(12, 45)))
        self.assertEqual(booking.requirementsSnapshot, "Theatre for 120, stage, wheelchair access")
        self.assertEqual(booking.coordinatorNotes, "Please keep the side doors open.")
        self.assertIsNotNone(booking.createdAt)


class TestAReasonIsRequired(RejectionCase):
    """AC2: no reason, no rejection; the request stays pending."""

    def test_a_missing_or_blank_reason_is_refused(self):
        a = self.request("e-a", at(10), at(12))
        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                detail = self.refused(lambda: self.reject(a, reason=reason), 422)
                self.assertEqual(detail, "Give a reason for rejecting this request.")
        self.assertEqual((self.stored(a).status, self.stored(a).reviewedBy), ("pending", None))

    def test_the_reason_is_stored_without_surrounding_spaces(self):
        a = self.request("e-a", at(10), at(12))

        self.assertEqual(self.reject(a, reason="  Too small for 120.  ").decisionReason, "Too small for 120.")


class TestASuggestedAlternative(RejectionCase):
    """AC3: another venue may be suggested; it is never required."""

    def test_no_suggestion_is_needed(self):
        rejected = self.reject(self.request("e-a", at(10), at(12)))

        self.assertEqual((rejected.status, rejected.suggestedVenueId, rejected.suggestedVenueName), ("rejected", None, None))

    def test_a_suggested_venue_is_kept_by_id_and_name(self):
        rejected = self.reject(self.request("e-a", at(10), at(12)), suggested=self.room.venueId)

        self.assertEqual((rejected.suggestedVenueId, rejected.suggestedVenueName), (self.room.venueId, "Riverside Room"))
        self.assertEqual(self.stored(rejected.bookingId).suggestedVenueName, "Riverside Room")

    def test_an_unknown_retired_or_same_venue_cannot_be_suggested(self):
        a = self.request("e-a", at(10), at(12))
        retired = self.service.create_venue(venue_create(code="OLD-1", name="Old Annex"), CALLER)
        self.service.retire_venue(retired.venueId, CALLER, confirm=True)
        cases = {
            "no-such-venue": "The suggested venue does not exist or has been retired. "
            "Choose another venue, or leave the suggestion empty.",
            retired.venueId: "The suggested venue does not exist or has been retired. "
            "Choose another venue, or leave the suggestion empty.",
            self.hall.venueId: "Suggest a different venue from the one being rejected, or leave the suggestion empty.",
        }
        for venue_id, message in cases.items():
            with self.subTest(venue_id=venue_id):
                self.assertEqual(self.refused(lambda: self.reject(a, suggested=venue_id), 422), message)
        self.assertEqual(self.stored(a).status, "pending")


class TestARejectedRequestIsClosed(RejectionCase):
    """AC4: Rejected, out of the pending queue, and no longer approvable or changeable."""

    def setUp(self):
        super().setUp()
        self.a = self.request("e-a", at(10), at(12))
        self.reject(self.a)

    def test_it_is_rejected_and_leaves_the_pending_queue(self):
        self.assertEqual(self.service.get_booking(self.a).status, "rejected")
        self.assertNotIn(self.a, self.queue("pending"))
        self.assertEqual(self.queue("rejected"), [self.a])

    def test_it_cannot_be_approved_or_rejected_again(self):
        self.assertEqual(self.refused(lambda: self.approve(self.a)), "Booking is already rejected")
        self.assertEqual(self.refused(lambda: self.reject(self.a)), "Booking is already rejected")

    def test_it_cannot_be_withdrawn_held_or_cancelled(self):
        self.assertIn(
            "Only a pending request can be withdrawn",
            self.refused(lambda: self.service.withdraw_booking(self.a, COORDINATOR, COORDINATOR["userId"])),
        )
        self.assertIn(
            "Only a pending booking request can be held",
            self.refused(lambda: self.service.place_hold(self.a, at(8) - timedelta(days=1), CALLER)),
        )
        self.assertIn(
            "Only an approved booking can be cancelled",
            self.refused(lambda: self.service.cancel_booking(self.a, CALLER, None)),
        )
        self.assertEqual(self.stored(self.a).status, "rejected")


class TestARejectedRequestReservesNothing(RejectionCase):
    """AC5: the venue is free again, and an active hold on the request is released."""

    def test_rejecting_a_held_request_releases_the_venue(self):
        a = self.request("e-a", at(10), at(12))
        self.service.place_hold(a, at(8) - timedelta(days=1), CALLER)
        b = self.request("e-b", at(12), at(13))  # set up from 11:30, inside A's held window
        self.assertIn("on a tentative hold", self.refused(lambda: self.approve(b)))

        rejected = self.reject(a)

        self.assertEqual((rejected.status, rejected.hold.state), ("rejected", "rejected"))
        self.assertTrue(self.free(at(10), at(12)))
        self.assertEqual(self.approve(b).status, "approved")

    def test_a_rejected_request_never_blocks_an_overlapping_approval(self):
        a = self.request("e-a", at(10), at(12))
        self.reject(a)

        self.assertEqual(self.approve(self.request("e-b", at(10), at(12))).status, "approved")


class TestTheRejectionRecord(RejectionCase):
    """AC6: who rejected it, the reason, and when."""

    def test_who_why_and_when_are_kept(self):
        a = self.request("e-a", at(10), at(12))
        before = datetime.utcnow()
        self.reject(a, reason="The stage is being rebuilt.", name="Vinod Kumar")
        after = datetime.utcnow()

        stored = self.stored(a)
        self.assertEqual(
            (stored.reviewedBy, stored.reviewedByName, stored.decisionReason),
            ("u-venue", "Vinod Kumar", "The stage is being rebuilt."),
        )
        self.assertTrue(before <= stored.reviewedAt <= after)


class TestATentativeHoldExpires(RejectionCase):
    """AC7: a hold lasts until its expiry time exactly, then releases the venue and is not a confirmed booking."""

    def test_a_hold_is_active_until_its_expiry_time_and_then_reserves_nothing(self):
        held = self.request("e-b", at(12), at(13))
        self.service.place_hold(held, at(8) - timedelta(days=1), CALLER)
        row = self.db.get(VenueBooking, held)
        expiry = row.holdExpiresAt
        self.assertEqual(hold_state(row, expiry - timedelta(seconds=1)), "active")
        self.assertEqual(hold_state(row, expiry), "expired")

        row.holdExpiresAt = datetime.utcnow() - timedelta(seconds=1)
        self.db.commit()

        self.assertTrue(self.free(at(12), at(13)))
        self.assertEqual(self.approve(self.request("e-a", at(10), at(12))).status, "approved")
        self.assertEqual(self.service.get_booking(held).status, "pending")
        self.assertNotIn(held, self.queue("approved"))


class TestPendingRequestsWait(RejectionCase):
    """AC8: a request with no hold stays pending until Venue Staff decide, however long that takes."""

    def test_an_old_request_without_a_hold_is_still_pending(self):
        a = self.request("e-a", at(10), at(12))
        self.db.get(VenueBooking, a).createdAt = datetime.utcnow() - timedelta(days=90)
        self.db.commit()

        self.assertEqual(self.service.get_booking(a).status, "pending")
        self.assertEqual(self.queue("pending"), [a])
        self.assertIsNone(self.service.get_booking(a).hold)

    def test_it_leaves_the_queue_only_when_approved_or_rejected(self):
        a, b = self.request("e-a", at(10), at(12)), self.request("e-b", at(14), at(15))

        self.approve(a)
        self.reject(b)

        self.assertEqual(self.queue("pending"), [])


class TestRejectionRoute(RejectionCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, booking_id, body):
        return self.client.post(f"/venues/bookings/{booking_id}/reject", headers=HEADERS, json=body)

    def test_venue_staff_reject_with_a_reason_and_a_suggestion_recorded_by_name(self):
        a = self.request("e-a", at(10), at(12))

        with signed_in_as("venue"):
            rejected = self.post(a, {"reason": "Closed that week.", "suggestedVenueId": self.room.venueId})

        self.assertEqual(rejected.status_code, 200, rejected.text)
        body = rejected.json()
        self.assertEqual(
            (body["status"], body["reviewedBy"], body["reviewedByName"], body["decisionReason"], body["suggestedVenueName"]),
            ("rejected", "u-venue", "venue", "Closed that week.", "Riverside Room"),
        )

    def test_a_blank_or_overlong_reason_is_refused(self):
        a = self.request("e-a", at(10), at(12))
        with signed_in_as("venue"):
            blank = self.post(a, {})
            too_long = self.post(a, {"reason": "x" * 2001})
            longest = self.post(a, {"reason": "x" * 2000})

        self.assertEqual((blank.status_code, blank.json()["detail"]), (422, "Give a reason for rejecting this request."))
        self.assertEqual(too_long.status_code, 422)
        self.assertEqual(longest.status_code, 200)

    def test_only_venue_staff_can_reject(self):
        a = self.request("e-a", at(10), at(12))
        for role in ("coordinator", "organiser", "techsupport", "safety", "attendee"):
            with self.subTest(role=role), signed_in_as(role):
                self.assertEqual(self.post(a, {"reason": "No"}).status_code, 403)
        self.assertEqual(self.service.get_booking(a).status, "pending")
