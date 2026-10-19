from datetime import timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import notify_role
from app.schemas.venue import EventFacts, OperatingHours, UnavailabilityCreate
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, END, START, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

OPEN = [OperatingHours(day=day, opens="00:00", closes="23:59") for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")]


class ReverificationCase(VenueCase):
    def setUp(self):
        super().setUp()
        self.venue_id = self.service.create_venue(venue_create(), CALLER).venueId

    def booking(self, event_id="e1", approve=True, days_later=0):
        # Different events need different days: two overlapping confirmed bookings
        # can no longer exist (SPM-64).
        shift = timedelta(days=days_later)
        created = self.service.create_booking(
            booking_create(self.venue_id, eventId=event_id, startsAt=START + shift, endsAt=END + shift), "u-coord"
        )
        if approve:
            self.service.approve_booking(created.bookingId, "u-venue", "Free")
        return created.bookingId


class TestBookingReverification(ReverificationCase):
    def test_only_the_events_approved_bookings_are_flagged_and_stay_approved(self):
        approved = self.booking()
        pending = self.booking(approve=False)
        other_event = self.booking(event_id="e2", days_later=1)

        flagged = self.service.flag_for_reverification("e1", "Expected attendance: 20 -> 200")

        self.assertEqual([row.bookingId for row in flagged], [approved])
        self.assertTrue(flagged[0].needsReverification)
        self.assertEqual(flagged[0].status, "approved")
        self.assertEqual(flagged[0].reverificationNote, "Expected attendance: 20 -> 200")
        self.assertEqual(flagged[0].venueName, "Marina Hall A")
        self.assertTrue(self.service.get_booking(approved).needsReverification)
        self.assertFalse(self.service.get_booking(pending).needsReverification)
        self.assertFalse(self.service.get_booking(other_event).needsReverification)

    def test_a_flagged_booking_still_holds_the_venue(self):
        approved = self.booking()
        self.service.flag_for_reverification("e1", "Start moved")

        venue = self.service.get_venue(self.venue_id)
        held = self.service.commitments(venue, START, END, exclude_event_id="another-event")

        self.assertEqual([row.bookingId for row in held.confirmed], [approved])

    def test_an_event_without_a_confirmed_booking_flags_nothing(self):
        self.booking(approve=False)

        self.assertEqual(self.service.flag_for_reverification("e1", "Start moved"), [])

    def test_a_new_booking_is_not_flagged(self):
        created = self.service.get_booking(self.booking(approve=False))

        self.assertFalse(created.needsReverification)
        self.assertIsNone(created.reverificationNote)


class TestBookingReverificationRoute(ReverificationCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_a_coordinator_can_flag_an_events_bookings(self):
        approved = self.booking()

        with signed_in_as("coordinator"):
            flagged = self.client.post(
                "/venues/bookings/reverification", headers=HEADERS, json={"eventId": "e1", "reason": "Start moved"}
            )

        self.assertEqual(flagged.status_code, 200)
        self.assertEqual([row["bookingId"] for row in flagged.json()], [approved])
        self.assertTrue(flagged.json()[0]["needsReverification"])

    def test_a_safety_officer_can_flag_an_events_bookings_for_review_again(self):
        approved = self.booking()

        with signed_in_as("safety"):
            flagged = self.client.post(
                "/venues/bookings/reverification",
                headers=HEADERS,
                json={"eventId": "e1", "reason": "Safety review: widen the aisles"},
            )

        self.assertEqual(flagged.status_code, 200)
        self.assertEqual([row["bookingId"] for row in flagged.json()], [approved])
        self.assertEqual(flagged.json()[0]["reverificationNote"], "Safety review: widen the aisles")

    def test_other_roles_cannot_flag_bookings(self):
        self.booking()
        for role in ("venue", "organiser", "techsupport", "attendee"):
            with signed_in_as(role):
                denied = self.client.post("/venues/bookings/reverification", headers=HEADERS, json={"eventId": "e1"})
            self.assertEqual(denied.status_code, 403, role)
        self.assertFalse(self.service.list_bookings(event_id="e1")[0].needsReverification)

    def test_recheck_reports_without_moving_and_reconfirm_answers_on_the_route(self):
        booking_id = self.booking()
        self.service.flag_for_reverification("e1", "Start moved")
        before = self.service.get_booking(booking_id).startsAt
        facts = EventFacts(expectedAttendance=20, layoutPreference="Classroom", proposedStartAt=START, proposedEndAt=END)

        with signed_in_as("venue"), patch("app.routers.venue.fetch_event_facts", return_value=facts):
            checked = self.client.post(
                f"/venues/bookings/{booking_id}/recheck",
                headers=HEADERS,
                json={"proposedStartAt": START.isoformat(), "proposedEndAt": END.isoformat()},
            )
            answered = self.client.post(f"/venues/bookings/{booking_id}/reconfirm", headers=HEADERS)

        self.assertEqual(checked.status_code, 200)
        self.assertFalse(checked.json()["movedSilently"])
        self.assertEqual(self.service.get_booking(booking_id).startsAt, before)
        self.assertIn(answered.status_code, (200, 409))


class OpenVenue(VenueCase):
    def setUp(self):
        super().setUp()
        self.venue_id = self.service.create_venue(venue_create(operatingHours=OPEN), CALLER).venueId

    def event(self, **overrides):
        facts = dict(
            expectedAttendance=20,
            layoutPreference="Classroom",
            proposedStartAt=START,
            proposedEndAt=END,
            eventName="Workshop",
            status="reconsidering",
            coordinatorId="u-coord",
        )
        facts.update(overrides)
        return EventFacts(**facts)

    def flagged(self):
        booking_id = self.service.create_booking(booking_create(self.venue_id), "u-coord").bookingId
        self.service.approve_booking(booking_id, "u-venue", "Free")
        self.service.flag_for_reverification("e1", "Start moved")
        return booking_id


class TestBookingRecheck(OpenVenue):
    def test_a_recheck_reports_a_clash_and_leaves_the_booking_where_it_is(self):
        booking_id = self.flagged()
        before = self.service.get_booking(booking_id)
        self.service.record_unavailability(
            self.venue_id,
            UnavailabilityCreate(startsAt=START, endsAt=END, reason="maintenance", acknowledgeConflicts=True),
            CALLER,
        )

        report = self.service.recheck_booking(booking_id, self.event(), START, END)
        after = self.service.get_booking(booking_id)

        self.assertTrue(report.conflict)
        self.assertFalse(report.movedSilently)
        self.assertEqual((after.startsAt, after.endsAt, after.status), (before.startsAt, before.endsAt, "approved"))

    def test_reconfirm_moves_a_free_booking_onto_the_event_and_clears_the_flag(self):
        booking_id = self.flagged()
        later = (START + timedelta(days=2)).replace(hour=4, minute=0, second=0, microsecond=0)  # 12:00 SGT
        finish = later + timedelta(hours=4)

        saved = self.service.reconfirm_booking(booking_id, self.event(proposedStartAt=later, proposedEndAt=finish), None)

        self.assertEqual(saved.status, "approved")
        self.assertFalse(saved.needsReverification)
        self.assertEqual((saved.startsAt, saved.endsAt), (later, finish))

    def test_reconfirm_releases_only_the_unsuitable_booking(self):
        booking_id = self.flagged()
        other = self.service.create_booking(
            booking_create(self.venue_id, eventId="e2", startsAt=START + timedelta(days=3), endsAt=END + timedelta(days=3)),
            "u-coord",
        ).bookingId
        self.service.approve_booking(other, "u-venue", "Free")
        self.service.record_unavailability(
            self.venue_id,
            UnavailabilityCreate(startsAt=START, endsAt=END, reason="maintenance", acknowledgeConflicts=True),
            CALLER,
        )

        with self.assertRaises(HTTPException) as raised:
            self.service.reconfirm_booking(booking_id, self.event(), None)

        released = self.service.get_booking(booking_id)
        self.assertIn("Search for a venue again", str(raised.exception.detail))
        self.assertEqual(released.status, "cancelled")
        self.assertEqual(self.service.get_booking(other).status, "approved")

    def test_a_broken_window_and_a_booking_that_is_not_approved_are_refused(self):
        booking_id = self.flagged()
        pending = self.service.create_booking(
            booking_create(self.venue_id, eventId="e9", startsAt=START + timedelta(days=4), endsAt=END + timedelta(days=4)),
            "u-coord",
        ).bookingId

        broken = self.service.recheck_booking(booking_id, self.event(), START, START)
        with self.assertRaises(HTTPException):
            self.service.recheck_booking(pending, self.event(), START, END)
        with self.assertRaises(HTTPException):
            self.service.reconfirm_booking(pending, self.event(), None)

        self.assertEqual(broken.verdict, "not suitable")
        self.assertTrue(broken.conflict)

    def test_releasing_tells_the_coordinator_and_a_free_booking_settles(self):
        kept = self.flagged()
        later = (START + timedelta(days=2)).replace(hour=4, minute=0, second=0, microsecond=0)  # 12:00 SGT
        saved = self.service.reconfirm_booking(
            kept, self.event(proposedStartAt=later, proposedEndAt=later + timedelta(hours=4)), "Bearer token"
        )
        self.assertEqual(saved.status, "approved")
        self.assertFalse(saved.needsReverification)

        blocked_at = (START + timedelta(days=5)).replace(hour=4, minute=0, second=0, microsecond=0)  # 12:00 SGT
        blocked_id = self.service.create_booking(
            booking_create(self.venue_id, startsAt=blocked_at, endsAt=blocked_at + timedelta(hours=4)), "u-coord"
        ).bookingId
        self.service.approve_booking(blocked_id, "u-venue", "Free")
        self.service.flag_for_reverification("e1", "Start moved")
        self.service.record_unavailability(
            self.venue_id,
            UnavailabilityCreate(
                startsAt=blocked_at, endsAt=blocked_at + timedelta(hours=4), reason="maintenance", acknowledgeConflicts=True
            ),
            CALLER,
        )
        with self.assertRaises(HTTPException):
            self.service.reconfirm_booking(
                blocked_id,
                self.event(proposedStartAt=blocked_at, proposedEndAt=blocked_at + timedelta(hours=4)),
                "Bearer token",
            )
        self.assertEqual(self.service.get_booking(blocked_id).status, "cancelled")


class TestRoleNotice(VenueCase):
    def test_each_person_in_the_role_is_told(self):
        users = patch("app.orchestration.clients.httpx.get")
        posted = patch("app.orchestration.clients.httpx.post")
        with users as get, posted as post:
            listed = get.return_value
            listed.status_code = 200
            listed.json.return_value = [
                {"userId": "u3", "email": "vinod@x.com", "role": "venue"},
                {"userId": "u9", "email": "other@x.com", "role": "organiser"},
            ]
            post.return_value.status_code = 201
            sent = notify_role("venue", "e1", "A booking needs re-verification", "Check it", "Bearer token", "venue.reverification")
            listed.status_code = 503
            missed = notify_role("venue", "e1", "A booking needs re-verification", "Check it", "Bearer token", "venue.reverification")

        self.assertEqual(sent, 1)
        self.assertEqual(missed, 0)
        self.assertEqual(post.call_count, 2)
