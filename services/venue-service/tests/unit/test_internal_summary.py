from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.venue_booking import VenueBooking
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

    def test_it_needs_the_service_key(self):
        response = self.client.get("/internal/venues/bookings/public-summary", params={"eventId": "e1"})

        self.assertEqual(response.status_code, 403)
