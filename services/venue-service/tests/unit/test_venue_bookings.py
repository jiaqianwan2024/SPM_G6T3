from fastapi import HTTPException

from tests.unit.support import CALLER, VenueCase, booking_create, venue_create


class TestVenueBookings(VenueCase):
    def test_approve_and_reject_only_work_while_pending(self):
        created = self.service.create_venue(venue_create(), CALLER)
        booking = self.service.create_booking(booking_create(created.venueId), "u-coord")

        approved = self.service.approve_booking(booking.bookingId, "u-venue", "OK")
        self.assertEqual(approved.status, "approved")
        self.assertEqual(approved.decisionReason, "OK")

        with self.assertRaises(HTTPException) as ctx:
            self.service.reject_booking(booking.bookingId, "u-venue", "Too late")
        self.assertEqual(ctx.exception.status_code, 409)

        other = self.service.create_booking(booking_create(created.venueId, eventId="e9"), "u-coord")
        rejected = self.service.reject_booking(other.bookingId, "u-venue", "Not suitable")  # SPM-10 AC2: a reason is required
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(rejected.decisionReason, "Not suitable")

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_booking(other.bookingId, "u-venue", "Again")
        self.assertEqual(ctx.exception.status_code, 409)
