from datetime import timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.venue import BookingReschedule, BookingReschedulePreview, EventFacts, UnavailabilityCreate
from app.services import occupancy
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, COORDINATOR, END, START, VenueCase, booking_create, venue_create
from tests.unit.test_venue_reverification import OPEN
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

# A week later, 12:00 to 16:00 SGT, inside every opening hour.
NEW_START = (START + timedelta(days=7)).replace(hour=4, minute=0, second=0, microsecond=0)
NEW_END = NEW_START + timedelta(hours=4)


class RescheduleCase(VenueCase):
    def setUp(self):
        super().setUp()
        self.hall = self.service.create_venue(venue_create(operatingHours=OPEN), CALLER).venueId
        self.annex = self.service.create_venue(
            venue_create(code="EH-B", name="Exhibition Hall B", operatingHours=OPEN), CALLER
        ).venueId

    def event(self, **overrides):
        facts = dict(
            expectedAttendance=20,
            layoutPreference="Classroom",
            proposedStartAt=START,
            proposedEndAt=END,
            eventName="Workshop",
            status="planning",
            coordinatorId="u-coord",
        )
        facts.update(overrides)
        return EventFacts(**facts)

    def booking(self, venue_id, event_id="e1", approve=True, start=START, end=END):
        booking_id = self.service.create_booking(
            booking_create(venue_id, eventId=event_id, startsAt=start, endsAt=end), "u-coord"
        ).bookingId
        if approve:
            self.service.approve_booking(booking_id, "u-venue", "Free")
        return booking_id

    def taken_at_new_time(self, venue_id):
        """Another event's confirmed booking where e1 wants to move."""
        return self.booking(venue_id, event_id="e2", start=NEW_START, end=NEW_END)

    def preview(self, **facts):
        return self.service.preview_reschedule(
            BookingReschedulePreview(eventId="e1", startsAt=NEW_START, endsAt=NEW_END), COORDINATOR, self.event(**facts)
        )

    def apply(self, carry=True, caller=COORDINATOR, authorization=None, **facts):
        return self.service.reschedule_bookings(
            BookingReschedule(eventId="e1", startsAt=NEW_START, endsAt=NEW_END, reason="Speaker moved", carry=carry),
            caller,
            self.event(**facts),
            authorization,
        )


class TestPreview(RescheduleCase):
    """SPM-87 AC2 and AC5."""

    def test_free_and_suitable_venues_are_reported_and_nothing_moves(self):
        booking_id = self.booking(self.hall)

        [judged] = self.preview()

        self.assertEqual((judged.bookingId, judged.venueName), (booking_id, "Marina Hall A"))
        self.assertEqual((judged.free, judged.suitable, judged.verdict, judged.outcome), (True, True, "suitable", None))
        stored = self.service.get_booking(booking_id)
        self.assertEqual((stored.startsAt, stored.status), (START, "approved"))

    def test_a_venue_taken_at_the_new_time_is_not_free(self):
        self.booking(self.hall)
        self.taken_at_new_time(self.hall)

        [judged] = self.preview()

        self.assertEqual((judged.free, judged.suitable), (False, True))
        self.assertTrue(any("confirmed booking" in reason for reason in judged.reasons))

    def test_unavailability_at_the_new_time_is_not_free(self):
        self.booking(self.hall)
        self.service.record_unavailability(
            self.hall, UnavailabilityCreate(startsAt=NEW_START, endsAt=NEW_END, reason="maintenance"), CALLER
        )

        [judged] = self.preview()

        self.assertFalse(judged.free)

    def test_a_venue_that_no_longer_suits_the_event_is_not_suitable(self):
        self.booking(self.hall)

        [judged] = self.preview(expectedAttendance=60)  # the Classroom layout holds 40

        self.assertEqual((judged.free, judged.suitable, judged.verdict), (True, False, "not suitable"))

    def test_the_events_own_old_booking_never_stands_in_its_way(self):
        # Moving by one hour overlaps the event's own current window.
        shifted = BookingReschedulePreview(eventId="e1", startsAt=START + timedelta(hours=1), endsAt=END + timedelta(hours=1))
        self.booking(self.hall)

        [judged] = self.service.preview_reschedule(shifted, COORDINATOR, self.event())

        self.assertTrue(judged.free)

    def test_only_the_assigned_coordinator_and_a_real_period(self):
        self.booking(self.hall)
        other = {"userId": "u-other", "role": "coordinator"}

        with self.assertRaises(HTTPException) as denied:
            self.service.preview_reschedule(
                BookingReschedulePreview(eventId="e1", startsAt=NEW_START, endsAt=NEW_END), other, self.event()
            )
        with self.assertRaises(HTTPException) as backwards:
            self.service.preview_reschedule(
                BookingReschedulePreview(eventId="e1", startsAt=NEW_END, endsAt=NEW_START), COORDINATOR, self.event()
            )

        self.assertEqual((denied.exception.status_code, backwards.exception.status_code), (403, 422))


class TestApply(RescheduleCase):
    """SPM-87 AC3 to AC5."""

    def test_a_free_and_suitable_booking_is_carried_across_and_flagged_for_venue_staff(self):
        booking_id = self.booking(self.hall)

        [moved] = self.apply()

        self.assertEqual((moved.outcome, moved.status), ("carried", "approved"))
        stored = self.service.get_booking(booking_id)
        self.assertEqual((stored.startsAt, stored.endsAt), (NEW_START, NEW_END))
        self.assertEqual(
            (stored.setupStartsAt, stored.teardownEndsAt), occupancy.occupied_window(NEW_START, NEW_END, 30, 60)
        )
        self.assertTrue(stored.needsReverification)
        self.assertEqual(stored.reverificationNote, "Event rescheduled. Speaker moved. Re-confirm the booking at the new time.")

    def test_the_old_time_is_free_once_applied(self):
        self.booking(self.hall)
        venue = self.service.get_venue(self.hall)
        self.assertTrue(self.service.commitments(venue, START, END, exclude_event_id="e9").conflicts)

        self.apply()

        self.assertFalse(self.service.commitments(venue, START, END, exclude_event_id="e9").conflicts)

    def test_an_unavailable_venue_is_released_and_the_available_one_stays(self):
        carried = self.booking(self.hall)
        released = self.booking(self.annex)
        self.taken_at_new_time(self.annex)

        results = {row.bookingId: row for row in self.apply()}

        self.assertEqual(results[carried].outcome, "carried")
        self.assertEqual((results[released].outcome, results[released].status), ("released", "cancelled"))
        stored = self.service.get_booking(released)
        self.assertEqual((stored.status, stored.startsAt), ("cancelled", START))
        self.assertIn("Released when the event was rescheduled", stored.reverificationNote)
        self.assertFalse(stored.needsReverification)

    def test_choosing_not_to_carry_releases_every_approved_booking(self):
        booking_id = self.booking(self.hall)

        [released] = self.apply(carry=False)

        self.assertEqual(released.outcome, "released")
        self.assertIn("It was not carried across", self.service.get_booking(booking_id).reverificationNote)

    def test_a_pending_request_asks_for_the_new_time_and_an_earlier_start_ends_its_hold(self):
        pending = self.booking(self.hall, approve=False)
        self.service.place_hold(pending, START - timedelta(hours=1), CALLER)

        earlier = START - timedelta(days=2)
        [moved] = self.service.reschedule_bookings(
            BookingReschedule(eventId="e1", startsAt=earlier, endsAt=earlier + timedelta(hours=2), reason="Sooner"),
            COORDINATOR,
            self.event(),
        )

        stored = self.service.get_booking(pending)
        self.assertEqual((moved.outcome, stored.status, stored.startsAt), ("moved", "pending", earlier))
        self.assertEqual(stored.hold.state, "released")

    def test_venue_staff_are_asked_to_re_confirm_only_when_something_was_carried(self):
        self.booking(self.hall)
        with patch("app.services.venue_service.notify_role", return_value=1) as notify:
            self.apply(authorization="Bearer token")
        role, event_id, title, body = notify.call_args.args[:4]
        self.assertEqual((role, event_id, title), ("venue", "e1", "Re-confirm a rescheduled booking"))
        self.assertIn("Marina Hall A", body)
        self.assertIn("SGT", body)

        with patch("app.services.venue_service.notify_role", return_value=1) as notify:
            self.apply(carry=False, authorization="Bearer token")
        notify.assert_not_called()

    def test_only_the_assigned_coordinator(self):
        booking_id = self.booking(self.hall)

        with self.assertRaises(HTTPException) as denied:
            self.apply(caller={"userId": "u-other", "role": "coordinator"})

        self.assertEqual(denied.exception.status_code, 403)
        self.assertEqual(self.service.get_booking(booking_id).startsAt, START)

    def test_other_events_bookings_are_left_alone(self):
        other = self.booking(self.hall, event_id="e2", start=START + timedelta(days=3), end=END + timedelta(days=3))
        self.booking(self.annex)

        self.apply()

        self.assertEqual(self.service.get_booking(other).startsAt, START + timedelta(days=3))


class TestRescheduleRoutes(RescheduleCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_the_assigned_coordinator_previews_and_applies(self):
        booking_id = self.booking(self.hall)
        body = {"eventId": "e1", "startsAt": NEW_START.isoformat(), "endsAt": NEW_END.isoformat()}
        facts = self.event(coordinatorId="u-coordinator")

        with signed_in_as("coordinator"), patch("app.routers.venue.fetch_event_facts", return_value=facts), patch(
            "app.services.venue_service.notify_role", return_value=1
        ):
            preview = self.client.post("/venues/bookings/reschedule/preview", headers=HEADERS, json=body)
            applied = self.client.post("/venues/bookings/reschedule", headers=HEADERS, json={**body, "reason": "x"})

        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()[0]["free"], True)
        self.assertEqual(applied.status_code, 200)
        self.assertEqual(applied.json()[0]["outcome"], "carried")
        self.assertEqual(self.service.get_booking(booking_id).startsAt, NEW_START)

    def test_other_roles_are_refused(self):
        self.booking(self.hall)
        body = {"eventId": "e1", "startsAt": NEW_START.isoformat(), "endsAt": NEW_END.isoformat()}
        for role in ("venue", "organiser", "techsupport", "safety", "attendee"):
            with signed_in_as(role):
                preview = self.client.post("/venues/bookings/reschedule/preview", headers=HEADERS, json=body)
                applied = self.client.post("/venues/bookings/reschedule", headers=HEADERS, json=body)
            self.assertEqual((preview.status_code, applied.status_code), (403, 403), role)
