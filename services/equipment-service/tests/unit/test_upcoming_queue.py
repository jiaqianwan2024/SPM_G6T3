from datetime import date
from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import fetch_upcoming_events, fetch_venue_name
from app.schemas.equipment import EquipmentRequestCreate
from app.services.equipment_service import _equipment_state
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden
from tests.unit.support import CALLER, END, START, EquipmentCase, equipment_create


def event(event_id, start="2026-10-06T09:00:00", **extra):
    row = {
        "eventId": event_id,
        "eventName": f"Event {event_id}",
        "status": "confirmed",
        "proposedStartAt": start,
        "proposedEndAt": "2026-10-06T17:00:00",
        "coordinatorId": "u2",
        "equipmentLines": [],
    }
    row.update(extra)
    return row


def venue(event_id):
    return "Marina Hall A" if event_id == "e1" else ""


class TestUpcomingQueue(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.equipment_id = self.service.create_equipment(equipment_create(code="UPQ"), CALLER).equipmentId

    def request_for(self, event_id, status=None, quantity=1):
        made = self.service.create_request(
            EquipmentRequestCreate(
                eventId=event_id, equipmentId=self.equipment_id, quantity=quantity, startsAt=START, endsAt=END
            ),
            "u-coord",
        )
        if status:
            row = self.service.request_dao.get_by_id(made.requestId)
            row.status = status
            self.db.commit()
        return made

    def ids(self, rows):
        return [row.eventId for row in rows]

    def test_only_events_with_equipment_requirements_appear(self):
        self.request_for("e1")
        lines = event("e2", equipmentLines=[{"equipmentId": self.equipment_id, "quantity": 2}])

        rows = self.service.upcoming_queue([event("e1"), lines, event("e6")], venue)

        self.assertEqual(sorted(self.ids(rows)), ["e1", "e2"])

    def test_a_row_carries_the_details_the_queue_shows(self):
        self.request_for("e1", quantity=3)

        row = self.service.upcoming_queue([event("e1")], venue)[0]

        self.assertEqual(row.eventName, "Event e1")
        self.assertEqual(row.status, "confirmed")
        self.assertEqual(row.venueName, "Marina Hall A")
        self.assertEqual(row.coordinatorId, "u2")
        self.assertEqual(row.equipmentSummary, "3 × Projector")
        self.assertEqual(row.equipmentState, "awaiting_review")
        self.assertFalse(row.needsAttention)

    def test_equipment_lines_are_summarised_when_nothing_has_been_requested_yet(self):
        lines = event("e2", equipmentLines=[{"equipmentId": self.equipment_id, "quantity": 2}])

        row = self.service.upcoming_queue([lines], venue)[0]

        self.assertEqual(row.equipmentSummary, "2 × Projector")
        self.assertEqual(row.equipmentState, "awaiting_review")

    def test_cancelled_requests_do_not_count(self):
        self.request_for("e1", status="cancelled")

        self.assertEqual(self.service.upcoming_queue([event("e1")], venue), [])

    def test_events_are_ordered_soonest_first(self):
        for event_id in ("e1", "e2", "e3"):
            self.request_for(event_id)
        events = [
            event("e3", "2026-10-09T09:00:00"),
            event("e1", "2026-10-06T09:00:00"),
            event("e2", "2026-10-07T09:00:00"),
        ]

        self.assertEqual(self.ids(self.service.upcoming_queue(events, venue)), ["e1", "e2", "e3"])

    def test_an_event_without_a_start_goes_last(self):
        self.request_for("e1")
        self.request_for("e2")

        rows = self.service.upcoming_queue([event("e2", start=None), event("e1")], venue)

        self.assertEqual(self.ids(rows), ["e1", "e2"])

    def test_attention_comes_first_within_the_same_date_only(self):
        for event_id in ("e1", "e2", "e3"):
            self.request_for(event_id)
        self.request_for("e2", status="unavailable")
        events = [
            event("e1", "2026-10-06T09:00:00"),
            event("e2", "2026-10-06T15:00:00"),
            event("e3", "2026-10-05T09:00:00"),
        ]

        rows = self.service.upcoming_queue(events, venue)

        self.assertEqual(self.ids(rows), ["e3", "e2", "e1"])
        self.assertTrue(rows[1].needsAttention)

    def test_a_reservation_awaiting_reverification_is_flagged_and_listed_first(self):
        first = self.request_for("e1")
        self.request_for("e2")
        self.service.review_request(first.requestId, "u-tech", True, "OK")
        self.service.reserve_request(first.requestId)
        self.service.flag_for_reverification("e1", "Quantity rose")
        events = [event("e2", "2026-10-06T09:00:00"), event("e1", "2026-10-06T10:00:00")]

        rows = self.service.upcoming_queue(events, venue)

        self.assertEqual(self.ids(rows), ["e1", "e2"])
        self.assertTrue(rows[0].needsReverification)
        self.assertTrue(rows[0].needsAttention)

    def test_it_filters_by_equipment_state(self):
        self.request_for("e1", status="reserved")
        self.request_for("e2", status="unavailable")
        self.request_for("e3")
        events = [event("e1"), event("e2"), event("e3")]

        self.assertEqual(self.ids(self.service.upcoming_queue(events, venue, state="fully_reserved")), ["e1"])
        self.assertEqual(self.ids(self.service.upcoming_queue(events, venue, state="unavailable")), ["e2"])
        self.assertEqual(self.ids(self.service.upcoming_queue(events, venue, state="awaiting_review")), ["e3"])

    def test_it_filters_by_date_range_inclusive(self):
        for event_id in ("e1", "e2", "e3"):
            self.request_for(event_id)
        events = [
            event("e1", "2026-10-05T09:00:00"),
            event("e2", "2026-10-06T09:00:00"),
            event("e3", "2026-10-07T09:00:00"),
        ]

        rows = self.service.upcoming_queue(events, venue, date_from=date(2026, 10, 6), date_to=date(2026, 10, 6))

        self.assertEqual(self.ids(rows), ["e2"])

    def test_an_event_with_no_start_passes_the_date_filter(self):
        self.request_for("e1")

        rows = self.service.upcoming_queue([event("e1", start=None)], venue, date_from=date(2026, 10, 6))

        self.assertEqual(self.ids(rows), ["e1"])

    def test_a_timezone_aware_start_is_read(self):
        self.request_for("e1")

        row = self.service.upcoming_queue([event("e1", start="2026-10-06T09:00:00+00:00")], venue)[0]

        self.assertEqual(row.eventId, "e1")


class TestEquipmentState(EquipmentCase):
    def test_states_follow_the_request_statuses(self):
        self.assertEqual(_equipment_state([]), "awaiting_review")
        self.assertEqual(_equipment_state(["reserved", "complete"]), "fully_reserved")
        self.assertEqual(_equipment_state(["reserved", "pending"]), "partly_reserved")
        self.assertEqual(_equipment_state(["partial"]), "partly_reserved")
        self.assertEqual(_equipment_state(["reserved", "unavailable"]), "partly_reserved")
        self.assertEqual(_equipment_state(["unavailable", "pending"]), "unavailable")
        self.assertEqual(_equipment_state(["rejected"]), "unavailable")
        self.assertEqual(_equipment_state(["pending", "approved"]), "awaiting_review")


class TestUpcomingClients(EquipmentCase):
    def reply(self, status, body):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = body
        return response

    def test_upcoming_events_are_read_with_the_callers_token(self):
        with patch("app.orchestration.clients.httpx.get", return_value=self.reply(200, [{"eventId": "e1"}])) as get:
            rows = fetch_upcoming_events("Bearer token")

        self.assertEqual(rows, [{"eventId": "e1"}])
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_event_service_being_down_is_a_503(self):
        with patch("app.orchestration.clients.httpx.get", side_effect=httpx.ConnectError("down")):
            with self.assertRaises(Exception) as raised:
                fetch_upcoming_events("Bearer token")
        self.assertEqual(raised.exception.status_code, 503)

        with patch("app.orchestration.clients.httpx.get", return_value=self.reply(500, {})):
            with self.assertRaises(Exception) as raised:
                fetch_upcoming_events("Bearer token")
        self.assertEqual(raised.exception.status_code, 503)

    def test_the_venue_name_comes_from_the_booking_summary(self):
        with patch("app.orchestration.clients.httpx.get", return_value=self.reply(200, {"venueName": "Hall"})):
            self.assertEqual(fetch_venue_name("e1"), "Hall")
        with patch("app.orchestration.clients.httpx.get", return_value=self.reply(200, {"venueName": None})):
            self.assertEqual(fetch_venue_name("e1"), "")

    def test_a_missing_venue_service_leaves_the_venue_blank(self):
        with patch("app.orchestration.clients.httpx.get", side_effect=httpx.ConnectError("down")):
            self.assertEqual(fetch_venue_name("e1"), "")
        with patch("app.orchestration.clients.httpx.get", return_value=self.reply(500, {})):
            self.assertEqual(fetch_venue_name("e1"), "")


class TestUpcomingRoute(EquipmentCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_technical_support_get_the_queue(self):
        equipment_id = self.service.create_equipment(equipment_create(code="RTE"), CALLER).equipmentId
        self.service.create_request(
            EquipmentRequestCreate(eventId="e1", equipmentId=equipment_id, quantity=1, startsAt=START, endsAt=END),
            "u-coord",
        )
        with (
            patch("app.routers.equipment.resolve_caller", return_value=CALLER),
            patch("app.routers.equipment.fetch_upcoming_events", return_value=[event("e1"), event("e6")]),
            patch("app.routers.equipment.fetch_venue_name", return_value="Hall"),
        ):
            response = self.client.get(
                "/equipment/upcoming?state=awaiting_review&dateFrom=2026-10-01&dateTo=2026-10-31",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["eventId"] for row in response.json()], ["e1"])
        self.assertEqual(response.json()[0]["venueName"], "Hall")

    def test_anyone_else_is_refused(self):
        with patch("app.routers.equipment.resolve_caller", side_effect=forbidden()):
            response = self.client.get("/equipment/upcoming", headers=self.headers)

        self.assertEqual(response.status_code, 403)

    def test_an_unknown_state_is_rejected(self):
        with patch("app.routers.equipment.resolve_caller", return_value=CALLER):
            response = self.client.get("/equipment/upcoming?state=bogus", headers=self.headers)

        self.assertEqual(response.status_code, 422)
