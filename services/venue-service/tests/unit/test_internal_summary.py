from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.venue_booking import VenueBooking
from app.schemas.venue import Layout
from shared.testing.cases import ServiceTestCase
from tests.unit.support import CALLER, START, VenueCase, venue_create


class TestInternalPublicSummary(VenueCase):
    def setUp(self):
        super().setUp()
        self.key = patch.object(settings, "internal_service_key", "key-1")
        self.key.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.key.stop()
        super().tearDown()

    def test_a_service_reads_the_approved_venue_without_a_user_token(self):
        venue = self.service.create_venue(venue_create(), CALLER)
        self.db.add(
            VenueBooking(
                bookingId="b1",
                venueId=venue.venueId,
                eventId="e1",
                requestedBy="u-coord",
                status="approved",
                startsAt=START,
                endsAt=START + timedelta(hours=2),
                setupStartsAt=START,
                teardownEndsAt=START + timedelta(hours=3),
                createdAt=datetime.utcnow(),
            )
        )
        self.db.commit()

        response = self.client.get(
            "/internal/venues/bookings/public-summary",
            params={"eventId": "e1"},
            headers={"X-Service-Key": "key-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["venueName"], "Marina Hall A")

    def test_a_service_reads_what_the_active_venues_offer_each_once(self):
        # SPM-80: the organiser's requirement lists. A retired venue's offer does not count.
        self.service.create_venue(venue_create(), CALLER)
        self.service.create_venue(
            venue_create(
                code="RR-1",
                name="Riverside Room",
                layouts=[Layout(name="theatre", capacity=30), Layout(name="Boardroom", capacity=12)],
                facilities=["PA", "Whiteboard", " "],
                accessibility=["Ramp"],
            ),
            CALLER,
        )
        retired = self.service.create_venue(
            venue_create(code="OLD-1", name="Old Hall", facilities=["Smoke machine"]), CALLER
        )
        self.service.retire_venue(retired.venueId, CALLER, confirm=True)

        response = self.client.get("/internal/venues/catalogue-options", headers={"X-Service-Key": "key-1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "layouts": ["Theatre", "Classroom", "Boardroom"],
                "facilities": ["PA", "Whiteboard"],
                "accessibility": ["Ramp"],
            },
        )
        self.assertEqual(
            self.client.get("/internal/venues/catalogue-options").status_code, 403
        )

    def test_it_needs_the_service_key(self):
        response = self.client.get("/internal/venues/bookings/public-summary", params={"eventId": "e1"})

        self.assertEqual(response.status_code, 403)

    def test_a_service_reads_every_booking_of_one_event(self):
        # SPM-120: technical support send the handoff, but may not read venue bookings themselves.
        venue = self.service.create_venue(venue_create(), CALLER)
        for booking_id, event_id, status in (("b1", "e1", "approved"), ("b2", "e1", "pending"), ("b3", "e2", "approved")):
            self.db.add(
                VenueBooking(
                    bookingId=booking_id,
                    venueId=venue.venueId,
                    eventId=event_id,
                    requestedBy="u-coord",
                    status=status,
                    startsAt=START,
                    endsAt=START + timedelta(hours=2),
                    setupStartsAt=START,
                    teardownEndsAt=START + timedelta(hours=3),
                    createdAt=datetime.utcnow(),
                )
            )
        self.db.commit()

        response = self.client.get("/internal/venues/bookings", params={"eventId": "e1"}, headers={"X-Service-Key": "key-1"})
        refused = self.client.get("/internal/venues/bookings", params={"eventId": "e1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted((row["bookingId"], row["status"]) for row in response.json()), [("b1", "approved"), ("b2", "pending")])
        self.assertEqual(refused.status_code, 403)

    def test_several_events_are_summarised_in_one_call(self):
        # SPM-4: the upcoming queue names each event's venue without a call per event.
        venue = self.service.create_venue(venue_create(), CALLER)
        self.db.add(
            VenueBooking(
                bookingId="b1",
                venueId=venue.venueId,
                eventId="e1",
                requestedBy="u-coord",
                status="approved",
                startsAt=START,
                endsAt=START + timedelta(hours=2),
                setupStartsAt=START,
                teardownEndsAt=START + timedelta(hours=3),
                createdAt=datetime.utcnow(),
            )
        )
        self.db.commit()

        response = self.client.get(
            "/internal/venues/bookings/public-summaries",
            params={"eventIds": "e1, e2,,e1"},
            headers={"X-Service-Key": "key-1"},
        )
        refused = self.client.get("/internal/venues/bookings/public-summaries", params={"eventIds": "e1"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(sorted(response.json()), ["e1", "e2"])
        self.assertEqual(response.json()["e1"]["venueName"], "Marina Hall A")
        self.assertEqual(response.json()["e2"]["venueName"], "")
        self.assertEqual(refused.status_code, 403)

    def test_holds_that_ran_out_in_the_period_are_listed_with_their_venue(self):
        # SPM-93 AC4: event-service tells each coordinator when a hold expires.
        venue = self.service.create_venue(venue_create(), CALLER)
        now = datetime(2026, 11, 2, 9, 0)
        holds = (
            ("b-expired", now - timedelta(hours=3), None),
            ("b-released", now - timedelta(hours=2), now - timedelta(hours=5)),
            ("b-older", now - timedelta(days=3), None),
            ("b-active", now + timedelta(hours=2), None),
        )
        for booking_id, expires_at, ended_at in holds:
            self.db.add(
                VenueBooking(
                    bookingId=booking_id,
                    venueId=venue.venueId,
                    eventId="e1",
                    requestedBy="u-coord",
                    status="pending",
                    startsAt=START,
                    endsAt=START + timedelta(hours=2),
                    setupStartsAt=START,
                    teardownEndsAt=START + timedelta(hours=3),
                    createdAt=datetime.utcnow(),
                    holdExpiresAt=expires_at,
                    holdEndedAt=ended_at,
                )
            )
        self.db.commit()
        window = {"since": (now - timedelta(days=1)).isoformat() + "Z", "until": now.isoformat() + "Z"}

        response = self.client.get("/internal/venues/holds/expired", params=window, headers={"X-Service-Key": "key-1"})
        refused = self.client.get("/internal/venues/holds/expired", params=window)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(row["bookingId"], row["venueName"], row["expiresAt"]) for row in response.json()],
            [("b-expired", "Marina Hall A", "2026-11-02T06:00:00")],
        )
        self.assertEqual(refused.status_code, 403)
