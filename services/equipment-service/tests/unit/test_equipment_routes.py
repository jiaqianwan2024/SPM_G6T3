from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException

from fastapi.testclient import TestClient

from app.main import app
from app.orchestration.clients import check_event_access
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import CALLER, COORDINATOR, END, START


class TestEquipmentRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        # SPM-46: the coordinator in these flows is the one assigned to every event.
        self.assigned = patch("app.routers.equipment.fetch_event_coordinator", return_value=COORDINATOR["userId"])
        self.assigned.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.assigned.stop()
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_catalogue_request_and_reservation_routes(self):
        created = self.client.post(
            "/equipment",
            headers=self.headers,
            json={"code": "PX-200", "name": "Projector", "category": "display", "totalQuantity": 4},
        )
        self.assertEqual(created.status_code, 201)
        equipment_id = created.json()["equipmentId"]

        self.assertEqual(self.client.get("/equipment").status_code, 200)
        self.assertEqual(self.client.get(f"/equipment/{equipment_id}").status_code, 200)
        self.assertEqual(
            self.client.patch(
                f"/equipment/{equipment_id}",
                headers=self.headers,
                json={"name": "Projector Plus"},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(f"/equipment/{equipment_id}/activity-log").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/equipment/availability",
                json={"equipmentId": equipment_id, "startsAt": START.isoformat(), "endsAt": END.isoformat()},
            ).status_code,
            200,
        )
        reserved = self.client.post(
            "/equipment/reservations",
            headers=self.headers,
            json={
                "eventId": "e1",
                "equipmentId": equipment_id,
                "quantity": 1,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )
        self.assertEqual(reserved.status_code, 201)
        self.assertEqual(self.client.post("/equipment/availability", json={}).status_code, 422)
        listed = self.client.get(f"/equipment/{equipment_id}/reservations", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["status"], "active")

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        request = self.client.post(
            "/equipment/requests",
            headers=self.headers,
            json={
                "eventId": "e2",
                "equipmentId": equipment_id,
                "quantity": 1,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )
        self.assertEqual(request.status_code, 201)
        requests = self.client.get("/equipment/requests", headers=self.headers)
        self.assertEqual(requests.status_code, 200)
        self.assertTrue(any(row["eventId"] == "e2" for row in requests.json()))
        checked = self.client.post("/equipment/availability", json={"eventId": "e2"})
        self.assertEqual(checked.status_code, 200)
        self.assertTrue(checked.json()["canMeet"])
        self.assertEqual(checked.json()["lines"][0]["requestedQuantity"], 1)
        self.assertEqual(checked.json()["lines"][0]["availableQuantity"], 3)

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        self.assertEqual(
            self.client.post(
                f"/equipment/requests/{request.json()['requestId']}/review",
                headers=self.headers,
                json={"approve": True, "reviewNote": "OK"},
            ).status_code,
            200,
        )
        held = self.client.post(
            f"/equipment/requests/{request.json()['requestId']}/reserve",
            headers=self.headers,
        )
        self.assertEqual(held.status_code, 201)
        released = self.client.post(
            f"/equipment/reservations/{reserved.json()['reservationId']}/release",
            headers=self.headers,
            json={"reason": "done"},
        )
        self.assertEqual(released.status_code, 200)
        self.assertEqual(released.json()["status"], "released")

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        fresh = self.client.post(
            "/equipment/requests",
            headers=self.headers,
            json={
                "eventId": "e9",
                "equipmentId": equipment_id,
                "quantity": 1,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )
        self.assertEqual(fresh.status_code, 201)
        request_id = fresh.json()["requestId"]
        refined = self.client.patch(
            f"/equipment/requests/{request_id}/details",
            headers=self.headers,
            json={"quantity": 3, "technicalRequirements": "Wireless"},
        )
        self.assertEqual(refined.status_code, 200)
        self.assertEqual(refined.json()["quantity"], 3)
        self.assertEqual(refined.json()["status"], "pending")
        blank = self.client.post(
            f"/equipment/requests/{request_id}/unavailable",
            headers=self.headers,
            json={"reason": ""},
        )
        self.assertEqual(blank.status_code, 422)

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        opened = self.client.get(f"/equipment/requests/{request_id}", headers=self.headers)
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.json()["status"], "pending")
        with patch("app.services.equipment_service.publish_notification"):
            marked = self.client.post(
                f"/equipment/requests/{request_id}/unavailable",
                headers=self.headers,
                json={"reason": "insufficient stock", "note": "Only two exist"},
            )
        self.assertEqual(marked.status_code, 200)
        self.assertEqual(marked.json()["status"], "unavailable")
        self.assertEqual(marked.json()["reviewedBy"], "u-tech")
        self.assertTrue(marked.json()["reviewedAt"])
        denied = self.client.patch(
            f"/equipment/requests/{request_id}",
            headers=self.headers,
            json={"status": "reserved"},
        )
        self.assertEqual(denied.status_code, 403)

    def test_an_attendee_gets_403_on_the_staff_equipment_pages(self):
        # SPM-127 AC3: the catalogue, its log and an event's equipment are staff pages.
        created = self.client.post(
            "/equipment",
            headers=self.headers,
            json={"code": "PX-201", "name": "Projector", "category": "display", "totalQuantity": 1},
        ).json()
        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value={"userId": "att-1", "role": "attendee"})
        self.caller.start()

        for path in ["/equipment", f"/equipment/{created['equipmentId']}", f"/equipment/{created['equipmentId']}/activity-log",
                     "/equipment/reservations/summary?eventId=e1"]:
            with self.subTest(path=path):
                response = self.client.get(path, headers=self.headers)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["detail"], "Attendees can open only confirmed event pages and their own registrations.")

    def test_an_organiser_reads_the_equipment_summary_only_for_their_organisations_event(self):
        # SPM-47: event-service decides whether this organiser may open the event.
        from shared.exceptions.http import forbidden

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value={"userId": "org-9", "role": "organiser"})
        self.caller.start()
        refused = forbidden("You can only open your own organisation's events.")
        with patch("app.routers.equipment.check_event_access", side_effect=refused) as access:
            response = self.client.get("/equipment/reservations/summary?eventId=e1", headers=self.headers)
        self.assertEqual((response.status_code, response.json()["detail"]), (403, "You can only open your own organisation's events."))
        access.assert_called_once_with("e1", self.headers["Authorization"])

        with patch("app.routers.equipment.check_event_access") as allowed:
            self.assertEqual(self.client.get("/equipment/reservations/summary?eventId=e1", headers=self.headers).status_code, 200)
        allowed.assert_called_once()

    def test_staff_read_the_equipment_summary_without_an_organisation_check(self):
        with patch("app.routers.equipment.check_event_access") as access:
            response = self.client.get("/equipment/reservations/summary?eventId=e1", headers=self.headers)

        self.assertEqual(response.status_code, 200)
        access.assert_not_called()


class TestCheckEventAccess(ServiceTestCase):
    """The client asking event-service whether the caller may open an event (SPM-47)."""

    def respond(self, status_code, body=None, error=None):
        response = MagicMock(status_code=status_code)
        response.json.return_value = body or {}
        return patch("app.orchestration.clients.httpx.get", side_effect=error, return_value=response)

    def test_passes_when_event_service_lets_the_caller_open_the_event(self):
        with self.respond(200) as get:
            check_event_access("e1", "Bearer token")

        self.assertTrue(get.call_args.args[0].endswith("/events/e1"))
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_event_services_refusal_and_not_found_are_passed_on(self):
        cases = [(403, {"detail": "You can only open your own organisation's events."}, 403), (404, {}, 404)]
        for status_code, body, expected in cases:
            with self.subTest(status=status_code), self.respond(status_code, body), self.assertRaises(HTTPException) as ctx:
                check_event_access("e1", "Bearer token")
            self.assertEqual(ctx.exception.status_code, expected)

    def test_an_unreachable_or_failing_event_service_is_503(self):
        for stub in (self.respond(500), self.respond(0, error=httpx.ConnectError("down"))):
            with self.subTest(), stub, self.assertRaises(HTTPException) as ctx:
                check_event_access("e1", "Bearer token")
            self.assertEqual(ctx.exception.status_code, 503)
