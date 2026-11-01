"""SPM-108: a venue's calendar."""

from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_booking import VenueBooking
from app.models.venue_unavailability import VenueUnavailability
from app.orchestration.clients import find_event_facts
from app.schemas.venue import EventFacts, OperatingHours
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import not_found
from tests.unit.support import CALLER, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

MONDAY = datetime(2030, 1, 7)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def at(hour, minute=0, day=MONDAY):
    """`hour`:`minute` Singapore time, stored as naive UTC (eight hours earlier)."""
    return day + timedelta(hours=hour - 8, minutes=minute)


class CalendarCase(VenueCase):
    """Skyline Boardroom: open weekdays 08:00 to 18:00, 30 minutes setup and 45 minutes turnaround."""

    def setUp(self):
        super().setUp()
        self.room = self.service.create_venue(
            venue_create(
                name="Skyline Boardroom",
                setupMinutes=30,
                turnaroundMinutes=45,
                operatingHours=[OperatingHours(day=d, opens="08:00", closes="18:00") for d in WEEKDAYS],
            ),
            CALLER,
        ).venueId

    def request(self, event_id, start_hour, end_hour, day=MONDAY, snapshot=None, **fields):
        booking_id = self.service.create_booking(
            booking_create(self.room, eventId=event_id, startsAt=at(start_hour, day=day), endsAt=at(end_hour, day=day)),
            "u-coord",
            event_snapshot={"eventName": f"Event {event_id}", "clientOrganisation": "Apex Partners"}
            if snapshot is None
            else snapshot,
        ).bookingId
        row = self.db.get(VenueBooking, booking_id)
        for name, value in fields.items():
            setattr(row, name, value)
        self.db.commit()
        return booking_id

    def block(self, start, end, reason="maintenance"):
        row = VenueUnavailability(
            unavailabilityId=f"block-{start:%d%H%M}",
            venueId=self.room,
            startsAt=start,
            endsAt=end,
            reason=reason,
            note="Aircon",
            createdBy="u-venue",
        )
        self.db.add(row)
        self.db.commit()
        return row.unavailabilityId

    def calendar(self, starts_at=None, ends_at=None):
        return self.service.calendar(self.room, starts_at, ends_at, "Bearer token")

    def kinds(self, **kwargs):
        return {entry.id: entry.kind for entry in self.calendar(**kwargs).entries}


class TestCalendarEntries(CalendarCase):
    def test_ac1_every_kind_of_entry_is_on_the_calendar(self):
        future = datetime.utcnow() + timedelta(days=30)
        confirmed = self.request("e-a", 9, 10, status="approved")
        pending = self.request("e-b", 11, 12)
        held = self.request("e-c", 13, 14, holdExpiresAt=future, holdPlacedBy="u-venue")
        lapsed = self.request("e-d", 15, 16, holdExpiresAt=datetime(2020, 1, 1), holdPlacedBy="u-venue")
        block = self.block(at(16, 30), at(17, 30))

        self.assertEqual(
            self.kinds(),
            {confirmed: "confirmed", pending: "pending", held: "hold", lapsed: "expired-hold", block: "unavailable"},
        )

    def test_a_released_hold_shows_as_a_plain_pending_request(self):
        released = self.request(
            "e-a", 9, 10, holdExpiresAt=MONDAY, holdEndedAt=MONDAY - timedelta(days=2), holdEndReason="released"
        )

        self.assertEqual(self.kinds(), {released: "pending"})

    def test_closed_requests_hold_nothing_so_they_are_left_off(self):
        for status in ("rejected", "withdrawn", "cancelled"):
            self.request(f"e-{status}", 9, 10, status=status)

        self.assertEqual(self.calendar().entries, [])

    def test_ac3_a_booking_shows_its_occupied_window_and_the_events_advertised_times(self):
        self.request("e-a", 10, 12, status="approved")

        entry = self.calendar().entries[0]

        self.assertEqual((entry.startsAt, entry.endsAt), (at(9, 30), at(12, 45)))
        self.assertEqual((entry.eventStartsAt, entry.eventEndsAt), (at(10), at(12)))
        self.assertEqual(entry.booking.status, "approved")

    def test_ac4_a_booking_shows_its_event_name_and_client_organisation(self):
        self.request("e-a", 10, 12)

        entry = self.calendar().entries[0]

        self.assertEqual(
            (entry.eventId, entry.eventName, entry.clientOrganisation), ("e-a", "Event e-a", "Apex Partners")
        )

    def test_a_block_carries_its_record(self):
        block = self.block(at(9), at(11))

        entry = self.calendar().entries[0]

        self.assertEqual((entry.startsAt, entry.endsAt, entry.eventId), (at(9), at(11), None))
        self.assertEqual((entry.unavailability.unavailabilityId, entry.unavailability.note), (block, "Aircon"))

    def test_entries_are_earliest_first_and_the_venue_comes_with_its_opening_hours(self):
        later = self.request("e-a", 14, 15)
        block = self.block(at(9), at(10))
        earlier = self.request("e-b", 11, 12)

        calendar = self.calendar()

        self.assertEqual([entry.id for entry in calendar.entries], [block, earlier, later])
        self.assertEqual(
            (calendar.venueName, calendar.setupMinutes, calendar.turnaroundMinutes),
            ("Skyline Boardroom", 30, 45),
        )
        self.assertEqual(
            [(h.day, h.opens, h.closes) for h in calendar.operatingHours],
            [(d, "08:00", "18:00") for d in WEEKDAYS],
        )


class TestCalendarRange(CalendarCase):
    def test_a_booking_whose_setup_or_turnaround_reaches_into_the_range_is_shown(self):
        # Occupied 09:30 to 12:45. Setup reaches into a range ending 09:45; turnaround into one starting 12:30.
        booking = self.request("e-a", 10, 12)

        self.assertEqual(self.kinds(starts_at=at(8), ends_at=at(9, 45)), {booking: "pending"})
        self.assertEqual(self.kinds(starts_at=at(12, 30), ends_at=at(13)), {booking: "pending"})

    def test_windows_that_only_touch_the_range_are_not_shown(self):
        self.request("e-a", 10, 12)
        self.block(at(14), at(15))

        self.assertEqual(self.kinds(starts_at=at(8), ends_at=at(9, 30)), {})
        self.assertEqual(self.kinds(starts_at=at(12, 45), ends_at=at(14)), {})

    def test_ac9_a_range_with_nothing_in_it_is_an_empty_calendar(self):
        self.request("e-a", 10, 12)
        self.block(at(14), at(15))

        calendar = self.calendar(starts_at=at(9, day=MONDAY + timedelta(days=7)), ends_at=at(17, day=MONDAY + timedelta(days=7)))

        self.assertEqual(calendar.entries, [])

    def test_ac6_past_dates_are_shown_too(self):
        past = MONDAY.replace(year=2020)
        booking = self.request("e-a", 10, 12, day=past, status="approved")

        self.assertEqual(self.kinds(starts_at=past, ends_at=past + timedelta(days=1)), {booking: "confirmed"})

    def test_a_range_given_with_an_offset_is_read_as_utc(self):
        booking = self.request("e-a", 10, 12)
        sgt = datetime.fromisoformat("2030-01-07T10:00:00+08:00")

        self.assertEqual(self.kinds(starts_at=sgt, ends_at=sgt + timedelta(hours=1)), {booking: "pending"})

    def test_a_range_that_ends_before_it_starts_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            self.calendar(starts_at=at(12), ends_at=at(10))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_an_unknown_venue_is_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.calendar("missing", None, None, "Bearer token")
        self.assertEqual(ctx.exception.status_code, 404)


class TestCalendarEventDetails(CalendarCase):
    """Requests sent before SPM-63 carry no event details, so they are read from event-service."""

    def test_an_older_request_reads_its_event_once_per_event(self):
        self.request("e-old", 9, 10, snapshot={})
        self.request("e-old", 11, 12, snapshot={})
        event = EventFacts(eventName="AI in Events Summit", organisationId="o1", organisationName="Apex Partners")

        with patch("app.services.venue_service.find_event_facts", return_value=event) as lookup:
            entries = self.calendar().entries

        lookup.assert_called_once_with("e-old", "Bearer token")
        self.assertEqual(
            {(entry.eventName, entry.clientOrganisation) for entry in entries}, {("AI in Events Summit", "Apex Partners")}
        )

    def test_without_an_organisation_name_the_organisation_id_is_shown(self):
        self.request("e-old", 9, 10, snapshot={"eventName": ""})

        with patch("app.services.venue_service.find_event_facts", return_value=EventFacts(eventName="Summit", organisationId="o1")):
            entry = self.calendar().entries[0]

        self.assertEqual((entry.eventName, entry.clientOrganisation), ("Summit", "o1"))

    def test_an_event_with_no_organisation_shows_no_client(self):
        self.request("e-old", 9, 10, snapshot={})

        with patch("app.services.venue_service.find_event_facts", return_value=EventFacts(eventName="Summit")):
            entry = self.calendar().entries[0]

        self.assertEqual(entry.clientOrganisation, "")

    def test_an_event_that_cannot_be_read_still_shows_by_its_id(self):
        self.request("e-old", 9, 10, snapshot={})

        with patch("app.services.venue_service.find_event_facts", return_value=None):
            entry = self.calendar().entries[0]

        self.assertEqual((entry.eventName, entry.clientOrganisation), ("e-old", ""))

    def test_a_request_with_details_never_reads_the_event(self):
        self.request("e-a", 9, 10, snapshot={"eventName": "Summit"})

        with patch("app.services.venue_service.find_event_facts") as lookup:
            entry = self.calendar().entries[0]

        lookup.assert_not_called()
        self.assertEqual((entry.eventName, entry.clientOrganisation), ("Summit", ""))

    def test_find_event_facts_returns_the_event(self):
        event = EventFacts(eventName="Summit")

        with patch("app.orchestration.clients.fetch_event_facts", return_value=event) as fetch:
            self.assertIs(find_event_facts("e1", "Bearer token"), event)

        fetch.assert_called_once_with("e1", "Bearer token")

    def test_find_event_facts_returns_nothing_when_the_event_cannot_be_read(self):
        with patch("app.orchestration.clients.fetch_event_facts", side_effect=not_found("Event not found")):
            self.assertIsNone(find_event_facts("e1", "Bearer token"))


class TestCalendarRoute(CalendarCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def get(self, role, query=""):
        with signed_in_as(role):
            return self.client.get(f"/venues/{self.room}/calendar{query}", headers=HEADERS)

    def test_ac8_internal_roles_read_any_venues_calendar(self):
        booking = self.request("e-a", 10, 12)

        for role in ("coordinator", "coordinatorlead", "venue", "techsupport", "safety"):
            response = self.get(role)
            self.assertEqual(response.status_code, 200, role)
            self.assertEqual([entry["id"] for entry in response.json()["entries"]], [booking], role)

    def test_clients_cannot_read_a_venue_calendar(self):
        for role in ("organiser", "attendee"):
            self.assertEqual(self.get(role).status_code, 403, role)

    def test_the_range_is_taken_from_from_and_to(self):
        booking = self.request("e-a", 10, 12)

        inside = self.get("venue", "?from=2030-01-07T02:00:00Z&to=2030-01-07T03:00:00Z")
        outside = self.get("venue", "?from=2030-01-08T00:00:00Z&to=2030-01-09T00:00:00Z")

        self.assertEqual([entry["id"] for entry in inside.json()["entries"]], [booking])
        self.assertEqual((outside.status_code, outside.json()["entries"]), (200, []))

    def test_a_backwards_range_is_a_validation_error(self):
        self.assertEqual(self.get("venue", "?from=2030-01-08T00:00:00Z&to=2030-01-07T00:00:00Z").status_code, 422)
