"""Venue catalogue, the attendee-safe booking summary, and the booking workflow over HTTP and SQL."""

from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_booking import VenueBooking
from app.schemas.venue import EventFacts
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase

VENUE = {"userId": "u-venue", "userName": "Carol", "role": "venue"}
COORDINATOR = {"userId": "u-coord", "userName": "Ben", "role": "coordinator"}


class TestVenueWorkflow(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.venue.resolve_caller", return_value=VENUE)
        self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_catalogue_and_public_summary(self):
        gate = app.dependency_overrides.pop(require_authenticated_user)
        self.assertEqual(self.client.get("/venues").status_code, 401)
        app.dependency_overrides[require_authenticated_user] = gate
        created = self.client.post(
            "/venues",
            headers=self.headers,
            json={
                "code": "MH-A",
                "name": "Marina Hall A",
                "location": "HarbourFront Centre",
                "address": "1 HarbourFront Walk",
                "floor": "2",
                "description": "Main hall",
                "facilities": ["Projector"],
                "accessibility": ["Wheelchair accessible"],
                "layouts": [{"name": "Theatre", "capacity": 100}],
                "operatingHours": [{"day": "Mon", "opens": "08:00", "closes": "18:00"}],
                "setupMinutes": 30,
                "turnaroundMinutes": 60,
            },
        )
        self.assertEqual(created.status_code, 201)
        summary = self.client.get(
            "/venues/bookings/public-summary", headers=self.headers, params={"eventId": "e1"}
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["venueName"], "")
        listed = self.client.get("/venues", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["name"], "Marina Hall A")


def at(hour, minute=0):
    return datetime(2030, 1, 7, hour, minute)  # a Monday; all times are UTC


class TestVenueBookingWorkflow(ServiceTestCase):
    """SPM-61 to SPM-64, SPM-112 and SPM-122: a coordinator searches, checks and
    requests a venue, Venue Staff approve, and the rows are read back from SQL.
    The hall needs 30 minutes of setup and 45 of turnaround, so event A
    (10:00 to 12:00) holds it from 09:30 to 12:45."""

    EVENTS = {
        "e-a": (at(10), at(12)),
        "e-b": (at(12), at(13)),  # starts as A ends, but is set up from 11:30
        "e-c": (at(13, 15), at(14)),  # set up from 12:45, just as A's window ends
    }

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.who = VENUE
        self.patches = [
            patch("app.routers.venue.resolve_caller", side_effect=lambda *args, **kwargs: self.who),
            patch("app.routers.venue.fetch_event_facts", side_effect=self.event),
            patch("app.routers.venue.notify_venue_staff", return_value=1),
        ]
        self.notify = [started.start() for started in self.patches][2]
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for started in self.patches:
            started.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def event(self, event_id, authorization):
        starts_at, ends_at = self.EVENTS[event_id]
        return EventFacts(
            eventName=f"Event {event_id}",
            status="planning",
            coordinatorId=COORDINATOR["userId"],
            expectedAttendance=50,
            layoutPreference="Theatre",
            proposedStartAt=starts_at,
            proposedEndAt=ends_at,
        )

    def as_(self, who):
        self.who = who
        return self.client

    def stored(self, booking_id):
        self.db.expire_all()
        return self.db.get(VenueBooking, booking_id)

    def request(self, event_id):
        starts_at, ends_at = self.EVENTS[event_id]
        sent = self.as_(COORDINATOR).post(
            "/venues/bookings",
            headers=self.headers,
            json={
                "venueId": self.venue_id,
                "eventId": event_id,
                "startsAt": starts_at.isoformat(),
                "endsAt": ends_at.isoformat(),
                "acknowledgeWarnings": True,
            },
        )
        self.assertEqual(sent.status_code, 201, sent.text)
        return sent.json()["bookingId"]

    def approve(self, booking_id):
        return self.as_(VENUE).post(f"/venues/bookings/{booking_id}/approve", headers=self.headers, json={})

    def search_lists_the_hall(self, event_id):
        starts_at, ends_at = self.EVENTS[event_id]
        found = self.as_(COORDINATOR).get(
            "/venues/search",
            headers=self.headers,
            params={"startsAt": starts_at.isoformat(), "endsAt": ends_at.isoformat()},
        )
        self.assertEqual(found.status_code, 200)
        return self.venue_id in [row["venueId"] for row in found.json()]

    def test_search_check_request_approve_withdraw_and_flag_clashes(self):
        created = self.as_(VENUE).post(
            "/venues",
            headers=self.headers,
            json={
                "name": "Harbour Hall",
                "location": "HarbourFront Centre",
                "layouts": [{"name": "Theatre", "capacity": 100}],
                "operatingHours": [
                    {"day": day, "opens": "00:00", "closes": "24:00"}
                    for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
                ],
                "setupMinutes": 30,
                "turnaroundMinutes": 45,
            },
        )
        self.assertEqual(created.status_code, 201)
        self.venue_id = created.json()["venueId"]

        # SPM-61 and SPM-62: the free hall is found and suits event A.
        self.assertTrue(self.search_lists_the_hall("e-a"))
        checked = self.as_(COORDINATOR).post(
            "/venues/suitability", headers=self.headers, json={"eventId": "e-a", "venueId": self.venue_id}
        )
        self.assertEqual(checked.json()["verdict"], "suitable")

        # SPM-63 and SPM-112 AC1: each request is stored pending with the event's
        # facts and the venue's occupied window, and Venue Staff are told.
        a, b, c = (self.request(event_id) for event_id in ("e-a", "e-b", "e-c"))
        row = self.stored(a)
        self.assertEqual((row.status, row.eventSnapshot["eventName"]), ("pending", "Event e-a"))
        self.assertEqual((row.setupStartsAt, row.teardownEndsAt), (at(9, 30), at(12, 45)))
        self.assertEqual(self.notify.call_count, 3)

        # SPM-64 and SPM-112: once A is confirmed, B (event times that only touch)
        # is refused and C (windows that only touch) is approved.
        self.assertEqual(self.approve(a).status_code, 200)
        refused = self.approve(b)
        self.assertEqual(refused.status_code, 409)
        self.assertIn("including setup and turnaround", refused.json()["detail"])
        self.assertEqual(self.approve(c).status_code, 200)
        self.assertEqual([self.stored(booking).status for booking in (a, b, c)], ["approved", "pending", "approved"])
        self.assertEqual(self.stored(a).reviewedBy, VENUE["userId"])
        self.assertFalse(self.search_lists_the_hall("e-b"))

        # SPM-63 AC8: the coordinator withdraws B.
        withdrawn = self.as_(COORDINATOR).post(f"/venues/bookings/{b}/withdraw", headers=self.headers)
        self.assertEqual(withdrawn.status_code, 200)
        self.assertEqual(self.stored(b).status, "withdrawn")

        # SPM-122: a longer turnaround makes A reach into C's setup. The clash is
        # listed, and both bookings stay approved.
        self.assertEqual(self.as_(VENUE).get("/venues/bookings/clashes", headers=self.headers).json(), [])
        edited = self.as_(VENUE).patch(f"/venues/{self.venue_id}", headers=self.headers, json={"turnaroundMinutes": 60})
        self.assertEqual(edited.status_code, 200)
        clashes = self.as_(VENUE).get("/venues/bookings/clashes", headers=self.headers).json()
        self.assertEqual([(clash["first"]["eventId"], clash["second"]["eventId"]) for clash in clashes], [("e-a", "e-c")])
        self.assertEqual(
            (clashes[0]["overlapStartsAt"], clashes[0]["overlapEndsAt"]), ("2030-01-07T12:45:00", "2030-01-07T13:00:00")
        )
        self.assertEqual([self.stored(booking).status for booking in (a, c)], ["approved", "approved"])


class TestVenueHoldWorkflow(TestVenueBookingWorkflow):
    """SPM-116: Venue Staff hold event A's request; nobody else can be approved for
    that window until the hold expires, and rejecting a held request releases it.
    The rows are read back from SQL."""

    EVENTS = {**TestVenueBookingWorkflow.EVENTS, "e-d": (at(16), at(17))}
    test_search_check_request_approve_withdraw_and_flag_clashes = None  # run once, in its own class

    def hold(self, booking_id, expires_at):
        return self.as_(VENUE).post(
            f"/venues/bookings/{booking_id}/hold", headers=self.headers, json={"expiresAt": expires_at}
        )

    def test_hold_blocks_others_until_it_expires_and_rejecting_releases_it(self):
        created = self.as_(VENUE).post(
            "/venues",
            headers=self.headers,
            json={
                "name": "Harbour Hall",
                "location": "HarbourFront Centre",
                "layouts": [{"name": "Theatre", "capacity": 100}],
                "operatingHours": [
                    {"day": day, "opens": "00:00", "closes": "24:00"}
                    for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
                ],
                "setupMinutes": 30,
                "turnaroundMinutes": 45,
            },
        )
        self.venue_id = created.json()["venueId"]
        a, b = self.request("e-a"), self.request("e-b")

        with patch("app.routers.venue.notify_coordinator", return_value=True) as told:
            held = self.hold(a, "2030-01-04T08:00:00Z")
        self.assertEqual((held.status_code, held.json()["hold"]["state"]), (200, "active"))
        self.assertEqual(told.call_args.args[:2], (COORDINATOR["userId"], "e-a"))
        row = self.stored(a)
        self.assertEqual((row.status, row.holdExpiresAt, row.holdPlacedBy), ("pending", at(8) - timedelta(days=3), "u-venue"))

        # AC2: B's window (set up from 11:30) overlaps the held 09:30 to 12:45, so B waits.
        refused = self.approve(b)
        self.assertEqual(refused.status_code, 409)
        self.assertIn("on a tentative hold", refused.json()["detail"])
        self.assertFalse(self.search_lists_the_hall("e-b"))

        # AC3 and AC4: once the expiry passes the hold reserves nothing, and A is still only pending.
        row.holdExpiresAt = datetime.utcnow() - timedelta(minutes=1)
        self.db.commit()
        self.assertEqual(self.approve(b).status_code, 200)
        self.assertEqual([self.stored(booking).status for booking in (a, b)], ["pending", "approved"])

        # AC6: a fresh hold on D (16:00 to 17:00), then rejecting D, releases the venue.
        d = self.request("e-d")
        self.assertEqual(self.hold(d, "2030-01-05T08:00:00Z").status_code, 200)
        rejected = self.as_(VENUE).post(f"/venues/bookings/{d}/reject", headers=self.headers, json={"reason": "No"})
        self.assertEqual(rejected.json()["hold"]["state"], "rejected")
        self.assertEqual((self.stored(d).holdEndReason, self.stored(d).status), ("rejected", "rejected"))


class TestVenueApprovalWorkflow(TestVenueBookingWorkflow):
    """SPM-8: Venue Staff read the queue oldest first, an unavailability block refuses
    approval and leaves the request pending, and an approval is recorded with the
    approver's name and time and then stays locked. The rows are read back from SQL."""

    test_search_check_request_approve_withdraw_and_flag_clashes = None  # run once, in its own class

    def test_queue_block_approve_record_and_lock(self):
        created = self.as_(VENUE).post(
            "/venues",
            headers=self.headers,
            json={
                "name": "Harbour Hall",
                "location": "HarbourFront Centre",
                "layouts": [{"name": "Theatre", "capacity": 100}],
                "operatingHours": [
                    {"day": day, "opens": "00:00", "closes": "24:00"}
                    for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
                ],
                "setupMinutes": 30,
                "turnaroundMinutes": 45,
            },
        )
        self.venue_id = created.json()["venueId"]
        a, b = self.request("e-a"), self.request("e-b")

        # AC1 and AC11: the pending queue shows each request's facts, oldest first.
        queue = self.as_(VENUE).get(
            "/venues/bookings", headers=self.headers, params={"status": "pending", "venueId": self.venue_id}
        ).json()
        self.assertEqual([row["bookingId"] for row in queue], [a, b])
        self.assertEqual(
            (queue[0]["startsAt"], queue[0]["setupStartsAt"], queue[0]["eventSnapshot"]["layout"]),
            ("2030-01-07T10:00:00", "2030-01-07T09:30:00", "Theatre"),
        )

        # AC6: maintenance inside A's turnaround refuses approval; A stays pending, approved by nobody.
        blocked = self.as_(VENUE).post(
            f"/venues/{self.venue_id}/unavailability",
            headers=self.headers,
            json={"startsAt": "2030-01-07T12:30:00", "endsAt": "2030-01-07T13:00:00", "reason": "maintenance"},
        )
        self.assertEqual(blocked.status_code, 201, blocked.text)
        refused = self.approve(a)
        self.assertEqual(refused.status_code, 409)
        self.assertIn("is unavailable from", refused.json()["detail"])
        row = self.stored(a)
        self.assertEqual((row.status, row.reviewedBy, row.reviewedByName, row.reviewedAt), ("pending", None, None, None))

        # AC10 and AC5: once the block is removed, A is approved with who and when.
        removed = self.as_(VENUE).delete(
            f"/venues/{self.venue_id}/unavailability/{blocked.json()['unavailabilityId']}", headers=self.headers
        )
        self.assertEqual(removed.status_code, 204, removed.text)
        before = datetime.utcnow()
        approved = self.approve(a)
        self.assertEqual(approved.status_code, 200, approved.text)
        row = self.stored(a)
        self.assertEqual((row.status, row.reviewedBy, row.reviewedByName), ("approved", "u-venue", "Carol"))
        self.assertGreaterEqual(row.reviewedAt, before.replace(microsecond=0))

        # AC4 and AC7: A is locked, and B (set up from 11:30) is refused and stays pending.
        self.assertEqual(self.approve(a).status_code, 409)
        rejected = self.as_(VENUE).post(f"/venues/bookings/{a}/reject", headers=self.headers, json={"reason": "No"})
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.approve(b).status_code, 409)
        self.assertEqual([self.stored(booking).status for booking in (a, b)], ["approved", "pending"])
        self.assertEqual(self.stored(a).reviewedByName, "Carol")


class TestVenueRejectionWorkflow(TestVenueBookingWorkflow):
    """SPM-10: Venue Staff reject a held request with a reason and a suggested venue. The
    request leaves the queue, its hold ends so another event can be approved there, and
    who, why, when and the suggestion are read back from SQL."""

    test_search_check_request_approve_withdraw_and_flag_clashes = None  # run once, in its own class

    def make_venue(self, name):
        created = self.as_(VENUE).post(
            "/venues",
            headers=self.headers,
            json={
                "name": name,
                "location": "HarbourFront Centre",
                "layouts": [{"name": "Theatre", "capacity": 100}],
                "operatingHours": [
                    {"day": day, "opens": "00:00", "closes": "24:00"}
                    for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
                ],
                "setupMinutes": 30,
                "turnaroundMinutes": 45,
            },
        )
        self.assertEqual(created.status_code, 201, created.text)
        return created.json()["venueId"]

    def reject(self, booking_id, body):
        return self.as_(VENUE).post(f"/venues/bookings/{booking_id}/reject", headers=self.headers, json=body)

    def test_reject_with_reason_and_suggestion_then_the_venue_is_free(self):
        self.venue_id = self.make_venue("Harbour Hall")
        suggested = self.make_venue("Riverside Room")
        a, b = self.request("e-a"), self.request("e-b")
        held = self.as_(VENUE).post(
            f"/venues/bookings/{a}/hold", headers=self.headers, json={"expiresAt": "2030-01-06T08:00:00Z"}
        )
        self.assertEqual(held.status_code, 200, held.text)
        self.assertEqual(self.approve(b).status_code, 409)  # A's hold covers B's setup

        # AC2: no reason, no rejection.
        blank = self.reject(a, {"reason": "  "})
        self.assertEqual((blank.status_code, blank.json()["detail"]), (422, "Give a reason for rejecting this request."))
        self.assertEqual(self.stored(a).status, "pending")

        # AC3 to AC6: rejected with a reason and a suggestion, recorded with who and when.
        before = datetime.utcnow()
        rejected = self.reject(a, {"reason": "The stage is being rebuilt.", "suggestedVenueId": suggested})
        self.assertEqual(rejected.status_code, 200, rejected.text)
        row = self.stored(a)
        self.assertEqual(
            (row.status, row.decisionReason, row.reviewedBy, row.reviewedByName, row.suggestedVenueId, row.suggestedVenueName),
            ("rejected", "The stage is being rebuilt.", "u-venue", "Carol", suggested, "Riverside Room"),
        )
        self.assertGreaterEqual(row.reviewedAt, before.replace(microsecond=0))
        self.assertEqual((row.holdEndReason, row.holdEndedAt is not None), ("rejected", True))
        queue = self.as_(VENUE).get(
            "/venues/bookings", headers=self.headers, params={"status": "pending", "venueId": self.venue_id}
        ).json()
        self.assertEqual([item["bookingId"] for item in queue], [b])

        # AC4 and AC5: it can no longer be approved, and it reserves nothing, so B is approved.
        self.assertEqual(self.approve(a).status_code, 409)
        self.assertEqual(self.approve(b).status_code, 200)
        self.assertEqual([self.stored(booking).status for booking in (a, b)], ["rejected", "approved"])
