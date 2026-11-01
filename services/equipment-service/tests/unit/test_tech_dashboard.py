"""SPM-58: technical support's home screen."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.equipment_request import EquipmentRequest
from app.models.equipment_reservation import EquipmentReservation
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden
from tests.unit.support import CALLER, END, START, EquipmentCase, equipment_create

HEADERS = {"Authorization": "Bearer token"}


def event(event_id, start, name=None):
    return {
        "eventId": event_id,
        "eventName": f"Event {event_id}" if name is None else name,
        "proposedStartAt": start,
        "proposedEndAt": start.replace("09:00", "17:00"),
    }


# Upcoming live events, soonest first, as event-service returns them.
SOONER = event("e-soon", "2030-01-07T09:00:00")
LATER = event("e-late", "2030-02-07T09:00:00")


class DashboardCase(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.projector = self.service.create_equipment(equipment_create(code="PX", name="Projector"), CALLER).equipmentId

    def request(self, request_id, event_id, status="pending", quantity=2, **fields):
        row = EquipmentRequest(
            requestId=request_id,
            eventId=event_id,
            equipmentId=self.projector,
            quantity=quantity,
            technicalRequirements=f"Needs for {request_id}",
            requestedBy="u-coord",
            status=status,
            startsAt=START,
            endsAt=END,
            **fields,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def reservation(self, reservation_id, event_id, status="active", quantity=2, **fields):
        request = self.request(f"req-{reservation_id}", event_id, status="reserved", quantity=quantity)
        row = EquipmentReservation(
            reservationId=reservation_id,
            requestId=request.requestId,
            eventId=event_id,
            equipmentId=self.projector,
            quantity=quantity,
            startsAt=START,
            endsAt=END,
            status=status,
            **fields,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def dashboard(self, events=(SOONER, LATER)):
        return self.service.technical_dashboard(list(events))


class TestPendingRequests(DashboardCase):
    def test_ac1_requests_awaiting_review_show_their_event_and_date_soonest_first(self):
        self.request("later", "e-late")
        self.request("sooner", "e-soon")
        self.request("done", "e-soon", status="reserved")

        pending = self.dashboard().pending

        self.assertEqual([row.id for row in pending], ["sooner", "later"])
        first = pending[0]
        self.assertEqual((first.eventName, first.eventStartsAt.isoformat()), ("Event e-soon", "2030-01-07T09:00:00"))
        self.assertEqual((first.equipmentName, first.quantity, first.note), ("Projector", 2, "Needs for sooner"))

    def test_an_event_without_a_name_shows_its_id(self):
        self.request("r1", "e-blank")

        self.assertEqual(self.dashboard([event("e-blank", "2030-01-07T09:00:00", name="")]).pending[0].eventName, "e-blank")

    def test_work_for_an_event_that_has_ended_or_was_cancelled_is_left_out(self):
        self.request("gone", "e-past")
        self.reservation("held-gone", "e-past", needsReverification=True)

        board = self.dashboard()

        self.assertEqual((board.pending, board.reverification, board.upcoming), ([], [], []))


class TestReverification(DashboardCase):
    def test_ac2_flagged_reservations_are_shown_with_what_changed(self):
        self.reservation("held-ok", "e-soon")
        self.reservation("held-flagged", "e-late", needsReverification=True, reverificationNote="Date moved")
        self.reservation("released", "e-soon", status="released", needsReverification=True)

        rows = self.dashboard().reverification

        self.assertEqual([(row.id, row.requestId, row.note) for row in rows], [("held-flagged", "req-held-flagged", "Date moved")])

    def test_a_flag_without_a_note_shows_no_note(self):
        self.reservation("held", "e-soon", needsReverification=True)

        self.assertEqual(self.dashboard().reverification[0].note, "")


class TestShortfalls(DashboardCase):
    def test_ac3_unavailable_and_partly_fulfilled_lines_are_shown_with_what_is_missing(self):
        self.request("partly", "e-late", status="partial", quantity=3, shortfall=1, reviewNote="One panel damaged")
        self.request("none", "e-soon", status="unavailable", quantity=2, decisionReason="All out for repair")

        rows = self.dashboard().shortfalls

        self.assertEqual(
            [(row.id, row.status, row.shortfall, row.note) for row in rows],
            [("none", "unavailable", 2, "All out for repair"), ("partly", "partial", 1, "One panel damaged")],
        )

    def test_a_shortfall_the_coordinator_accepted_is_resolved_and_left_out(self):
        self.request("accepted", "e-soon", status="resolved", shortfall=1)

        self.assertEqual(self.dashboard().shortfalls, [])


class TestUpcoming(DashboardCase):
    def test_ac4_events_with_equipment_held_are_shown_soonest_first(self):
        self.reservation("late-held", "e-late")
        self.reservation("soon-full", "e-soon", quantity=2)
        self.reservation("soon-part", "e-soon", status="partial", quantity=1)
        self.request("only-asked", "e-other")

        rows = self.dashboard([SOONER, LATER, event("e-other", "2030-03-01T09:00:00")]).upcoming

        self.assertEqual([row.eventId for row in rows], ["e-soon", "e-late"])
        self.assertEqual(rows[0].equipmentSummary, "2 × Projector, 1 × Projector")
        self.assertEqual(rows[0].eventName, "Event e-soon")

    def test_released_reservations_supply_nothing(self):
        self.reservation("gone", "e-soon", status="released")

        self.assertEqual(self.dashboard().upcoming, [])

    def test_ac7_with_nothing_waiting_every_section_is_empty(self):
        board = self.dashboard()

        self.assertEqual((board.pending, board.reverification, board.shortfalls, board.upcoming), ([], [], [], []))


class TestDashboardRoute(DashboardCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_technical_support_get_the_dashboard_for_the_upcoming_events(self):
        self.request("r1", "e-soon")

        with patch("app.routers.equipment.resolve_caller", return_value=CALLER), patch(
            "app.routers.equipment.fetch_upcoming_events", return_value=[SOONER]
        ) as upcoming:
            response = self.client.get("/equipment/dashboard", headers=HEADERS)

        upcoming.assert_called_once_with("Bearer token")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()["pending"]], ["r1"])

    def test_ac6_other_roles_are_refused_like_the_work_screens(self):
        with patch("app.routers.equipment.resolve_caller", side_effect=forbidden("nope")) as gate:
            response = self.client.get("/equipment/dashboard", headers=HEADERS)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(gate.call_args.kwargs["allowed_roles"], {"techsupport"})
