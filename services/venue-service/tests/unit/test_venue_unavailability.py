"""SPM-9: mark a venue unavailable, then change or remove the block.

An approved booking and a pending request with an active hold must be acknowledged.
The booking and the event stay as they are. Cancelling the block removes it.
"""

from datetime import datetime

from app.schemas.venue import UnavailabilityCreate, UnavailabilityUpdate
from tests.unit.test_venue_replacement import ReplacementCase, at
from tests.unit.support import CALLER


class TestUnavailabilityBlock(ReplacementCase):
    def test_a_note_is_kept_and_the_reason_must_be_one_of_the_list(self):
        saved = self.service.record_unavailability(
            self.venue.venueId,
            UnavailabilityCreate(startsAt=at(10), endsAt=at(12), reason="renovation", note="  Floor work  "),
            CALLER,
        )

        self.assertEqual((saved.reason, saved.note), ("renovation", "Floor work"))
        self.assertEqual(self.service.list_unavailability(self.venue.venueId)[0].note, "Floor work")
        self.assertIn("reason", self.refused(lambda: self.block(self.venue.venueId, reason="party"), 422))

    def test_an_active_hold_must_be_acknowledged_and_stays_pending(self):
        booking = self.request(self.venue.venueId)
        self.service.place_hold(booking.bookingId, at(9), CALLER)

        detail = self.refused(lambda: self.block(self.venue.venueId), 409)

        self.assertIn("e-mine", detail)
        self.assertIn("tentative hold", detail)
        saved = self.block(self.venue.venueId, acknowledge=True)
        kept = self.service.get_booking(booking.bookingId)
        self.assertEqual(kept.status, "pending")
        self.assertEqual(saved.venueId, self.venue.venueId)
        self.assertEqual(self.service.unavailability_alerts(self.venue.venueId, at(10), at(12))[0]["eventId"], "e-mine")

    def test_an_expired_or_released_hold_does_not_need_acknowledgement(self):
        expired = self.request(self.venue.venueId, "e-expired")
        row = self.service.booking_dao.list("pending", "e-expired", self.venue.venueId)[0]
        row.holdExpiresAt = datetime(2020, 1, 1)
        self.service.db.commit()

        self.block(self.venue.venueId, start=at(10), end=at(11))

        released = self.request(self.other.venueId, "e-released")
        held = self.service.booking_dao.list("pending", "e-released", self.other.venueId)[0]
        held.holdExpiresAt = at(9)
        held.holdEndedAt = datetime(2026, 1, 1)
        held.holdEndReason = "released"
        self.service.db.commit()
        self.block(self.other.venueId)
        self.assertEqual(self.service.get_booking(expired.bookingId).status, "pending")
        self.assertEqual(self.service.get_booking(released.bookingId).status, "pending")

    def test_changing_the_period_needs_confirmation_again_and_a_note_does_not(self):
        booking = self.approve(self.venue.venueId)
        saved = self.block(self.venue.venueId, acknowledge=True)

        noted = self.service.update_unavailability(
            self.venue.venueId, saved.unavailabilityId, UnavailabilityUpdate(note="updated note", reason="other"), CALLER
        )
        self.assertEqual((noted.note, noted.reason), ("updated note", "other"))
        detail = self.refused(
            lambda: self.service.update_unavailability(
                self.venue.venueId,
                saved.unavailabilityId,
                UnavailabilityUpdate(startsAt=at(9), endsAt=at(11)),
                CALLER,
            ),
            409,
        )
        self.assertIn("e-mine", detail)
        moved = self.service.update_unavailability(
            self.venue.venueId,
            saved.unavailabilityId,
            UnavailabilityUpdate(startsAt=at(9), endsAt=at(11), acknowledgeConflicts=True),
            CALLER,
        )
        self.assertEqual(moved.startsAt, at(9))
        self.assertEqual(self.service.get_booking(booking.bookingId).status, "approved")
        self.refused(
            lambda: self.service.update_unavailability(
                self.venue.venueId, saved.unavailabilityId, UnavailabilityUpdate(startsAt=at(12), endsAt=at(9)), CALLER
            ),
            422,
        )

    def test_cancelling_a_block_removes_it_and_frees_approval(self):
        booking = self.request(self.venue.venueId)
        saved = self.block(self.venue.venueId)
        self.refused(lambda: self.service.approve_booking(booking.bookingId, CALLER["userId"], None), 409)
        self.refused(
            lambda: self.service.update_unavailability(
                self.other.venueId, saved.unavailabilityId, UnavailabilityUpdate(note="x"), CALLER
            ),
            404,
        )

        self.service.cancel_unavailability(self.venue.venueId, saved.unavailabilityId, CALLER)

        self.assertEqual(self.service.list_unavailability(self.venue.venueId), [])
        self.assertEqual(self.service.approve_booking(booking.bookingId, CALLER["userId"], None).status, "approved")
        actions = " ".join(row.action for row in self.service.get_activity_log(self.venue.venueId))
        self.assertIn("unavailability created", actions)
        self.assertIn("unavailability cancelled", actions)
        self.refused(lambda: self.service.cancel_unavailability(self.venue.venueId, "missing", CALLER), 404)

    def test_a_pending_request_without_a_hold_is_not_an_alert(self):
        self.request(self.venue.venueId)
        self.block(self.venue.venueId)
        self.assertEqual(self.service.unavailability_alerts(self.venue.venueId, at(10), at(12)), [])
