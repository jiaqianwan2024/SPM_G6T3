import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException

from app.orchestration import clients

BOOKING = {
    "bookingId": "vb-1",
    "venueId": "v1",
    "venueName": "Marina Hall A",
    "startsAt": "2026-12-01T09:00:00",
    "endsAt": "2026-12-01T17:00:00",
    "status": "approved",
}
UNNAMED_BOOKING = {**BOOKING, "bookingId": "vb-2", "venueName": None}
HELD = {"reservationId": "er-1", "equipmentId": "eq1", "equipmentName": "Projector", "quantity": 2, "status": "active"}
RESERVED = {**HELD, "reservationId": "er-2", "equipmentName": None, "status": "reserved"}
RELEASED = {**HELD, "reservationId": "er-3", "status": "released"}


def reply(status_code, body=None):
    response = MagicMock(status_code=status_code)
    response.json.return_value = body
    return response


def fake_client(*responses):
    """Stands in for httpx.Client, answering each request in turn."""
    client = MagicMock()
    client.__enter__.return_value.request.side_effect = list(responses)
    return patch("app.orchestration.clients.httpx.Client", MagicMock(return_value=client)), client


class TestArrangementClients(unittest.TestCase):
    def test_affected_arrangements_names_confirmed_bookings_and_held_reservations(self):
        stub, client = fake_client(reply(200, [BOOKING, UNNAMED_BOOKING]), reply(200, [HELD, RESERVED, RELEASED]))
        with stub:
            affected = clients.affected_arrangements("e1", "Bearer token")

        self.assertEqual([row["id"] for row in affected], ["vb-1", "vb-2", "er-1", "er-2"])
        self.assertEqual(
            # Stored 09:00 to 17:00 UTC, read in Singapore time.
            affected[0]["summary"], "Venue booking at Marina Hall A, 01 Dec 2026 17:00 to 02 Dec 2026 01:00 SGT"
        )
        self.assertIn("at v1,", affected[1]["summary"])
        self.assertEqual(affected[2], {"kind": "equipment", "id": "er-1", "summary": "Equipment reservation: 2 x Projector"})
        self.assertIn("2 x eq1", affected[3]["summary"])
        venue_call, equipment_call = client.__enter__.return_value.request.call_args_list
        self.assertEqual(venue_call.args[0], "GET")
        self.assertTrue(venue_call.args[1].endswith("/venues/bookings"))
        self.assertEqual(venue_call.kwargs["params"], {"eventId": "e1", "status": "approved"})
        self.assertEqual(venue_call.kwargs["headers"], {"Authorization": "Bearer token"})
        self.assertTrue(equipment_call.args[1].endswith("/equipment/reservations"))

    def test_flag_arrangements_posts_the_reason_to_both_services(self):
        stub, client = fake_client(reply(200, [BOOKING]), reply(200, [HELD]))
        with stub:
            flagged = clients.flag_arrangements("e1", "Start moved", None)

        self.assertEqual([row["kind"] for row in flagged], ["venue", "equipment"])
        venue_call, equipment_call = client.__enter__.return_value.request.call_args_list
        self.assertEqual(venue_call.args[0], "POST")
        self.assertTrue(venue_call.args[1].endswith("/venues/bookings/reverification"))
        self.assertTrue(equipment_call.args[1].endswith("/equipment/reservations/reverification"))
        self.assertEqual(venue_call.kwargs["json"], {"eventId": "e1", "reason": "Start moved"})
        self.assertEqual(venue_call.kwargs["headers"], {})

    def test_a_refused_call_is_a_503(self):
        stub, _client = fake_client(reply(200, []), reply(403, {"detail": "Forbidden"}))
        with stub:
            with self.assertRaises(HTTPException) as ctx:
                clients.affected_arrangements("e1", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("not saved", ctx.exception.detail)

    def test_an_unreachable_service_is_a_503(self):
        with patch("app.orchestration.clients.httpx.Client", side_effect=httpx.ConnectError("down")):
            with self.assertRaises(HTTPException) as ctx:
                clients.flag_arrangements("e1", "Start moved", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 503)


class TestImpactClients(unittest.TestCase):
    """SPM-85: the reads behind a change request's impact assessment."""

    def test_confirmed_bookings_asks_for_the_events_approved_bookings(self):
        stub, client = fake_client(reply(200, [BOOKING]))
        with stub:
            self.assertEqual(clients.confirmed_bookings("e1", "Bearer token"), [BOOKING])

        request = client.__enter__.return_value.request.call_args
        self.assertTrue(request.args[1].endswith("/venues/bookings"))
        self.assertEqual(request.kwargs["params"], {"eventId": "e1", "status": "approved"})

    def test_venue_suitability_sends_the_proposed_values_for_one_venue(self):
        verdict = {"eventId": "e1", "venueId": "v1", "verdict": "suitable", "reasons": []}
        stub, client = fake_client(reply(200, verdict))
        needs = {"startsAt": "2026-12-08T09:00:00", "endsAt": "2026-12-08T17:00:00", "layout": "Banquet", "expectedAttendance": 90}
        with stub:
            self.assertEqual(clients.venue_suitability("e1", "v1", needs, "Bearer token"), verdict)

        request = client.__enter__.return_value.request.call_args
        self.assertEqual(request.args[0], "POST")
        self.assertTrue(request.args[1].endswith("/venues/suitability"))
        self.assertEqual(request.kwargs["json"], {"eventId": "e1", "venueId": "v1", **needs})

    def test_equipment_free_reads_the_quantity_free_in_the_period(self):
        stub, client = fake_client(
            reply(200, {"equipmentId": "eq1", "availableQuantity": 4, "serviceableQuantity": 6, "reservedQuantity": 2})
        )
        with stub:
            free = clients.equipment_free("eq1", datetime(2026, 12, 1, 9), datetime(2026, 12, 1, 17), "Bearer token")

        self.assertEqual(free, 4)
        request = client.__enter__.return_value.request.call_args
        self.assertTrue(request.args[1].endswith("/equipment/availability"))
        self.assertEqual(
            request.kwargs["json"],
            {"equipmentId": "eq1", "startsAt": "2026-12-01T09:00:00", "endsAt": "2026-12-01T17:00:00"},
        )

    def test_a_failed_read_is_a_503_naming_the_assessment(self):
        stub, _client = fake_client(reply(500, {}))
        with stub, self.assertRaises(HTTPException) as ctx:
            clients.confirmed_bookings("e1", None)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, clients.IMPACT_UNCHECKED)

    def test_venue_capacity_in_a_layout_or_its_largest(self):
        venue = {"capacity": 300, "layouts": [{"name": "Theatre", "capacity": 200}]}

        self.assertEqual(clients.venue_capacity_in(venue, "theatre"), {"layout": "theatre", "capacity": 200})
        self.assertEqual(clients.venue_capacity_in(venue, "Banquet"), {"layout": None, "capacity": 300})
        self.assertEqual(clients.venue_capacity_in(venue, None), {"layout": None, "capacity": 300})
