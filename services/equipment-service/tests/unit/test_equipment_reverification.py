from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.equipment import EquipmentAvailabilityIn, EquipmentQuantityReserve
from shared.auth.deps import require_authenticated_user
from fastapi import HTTPException

from shared.exceptions.http import forbidden
from tests.unit.support import CALLER, COORDINATOR, END, START, EquipmentCase, equipment_create


class ReverificationCase(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.equipment_id = self.service.create_equipment(equipment_create(totalQuantity=5), CALLER).equipmentId

    def reserve(self, event_id="e1", quantity=1):
        return self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId=event_id, equipmentId=self.equipment_id, quantity=quantity, startsAt=START, endsAt=END
            ),
            CALLER,
        ).reservationId


class TestReservationReverification(ReverificationCase):
    def test_only_the_events_held_reservations_are_flagged_and_keep_their_status(self):
        held = self.reserve()
        released = self.reserve()
        self.service.release_reservation(released, CALLER)
        other_event = self.reserve(event_id="e2")

        flagged = self.service.flag_for_reverification("e1", "Expected attendance: 20 -> 200")

        self.assertEqual([row.reservationId for row in flagged], [held])
        self.assertTrue(flagged[0].needsReverification)
        self.assertEqual(flagged[0].status, "active")
        self.assertEqual(flagged[0].reverificationNote, "Expected attendance: 20 -> 200")
        self.assertEqual(flagged[0].equipmentName, "Projector")
        by_id = {row.reservationId: row for row in self.service.list_event_reservations("e1")}
        self.assertEqual(set(by_id), {held, released})
        self.assertFalse(by_id[released].needsReverification)
        self.assertFalse(self.service.list_event_reservations("e2")[0].needsReverification)
        self.assertEqual(self.service.list_event_reservations("e2")[0].reservationId, other_event)

    def test_a_flagged_reservation_still_holds_its_stock(self):
        self.reserve(quantity=3)
        self.service.flag_for_reverification("e1", "Start moved")

        availability = self.service.check_availability(
            EquipmentAvailabilityIn(equipmentId=self.equipment_id, startsAt=START, endsAt=END)
        )

        self.assertEqual(availability.availableQuantity, 2)

    def test_an_event_without_reservations_flags_nothing(self):
        self.assertEqual(self.service.flag_for_reverification("e9", "Start moved"), [])
        self.assertEqual(self.service.list_event_reservations("e9"), [])


class TestReservationReverificationRoutes(ReverificationCase):
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

    def test_coordinators_list_and_flag_an_events_reservations(self):
        held = self.reserve()
        with patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR) as caller:
            listed = self.client.get("/equipment/reservations", params={"eventId": "e1"}, headers=self.headers)
            self.assertEqual(caller.call_args.kwargs["allowed_roles"], {"techsupport", "coordinator"})
            flagged = self.client.post(
                "/equipment/reservations/reverification",
                headers=self.headers,
                json={"eventId": "e1", "reason": "Start moved"},
            )
            self.assertEqual(caller.call_args.kwargs["allowed_roles"], {"coordinator", "safety"})

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["reservationId"] for row in listed.json()], [held])
        self.assertEqual(flagged.status_code, 200)
        self.assertTrue(flagged.json()[0]["needsReverification"])

    def test_listing_needs_an_event_id(self):
        with patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR):
            missing = self.client.get("/equipment/reservations", headers=self.headers)

        self.assertEqual(missing.status_code, 422)

    def test_a_refused_role_flags_nothing(self):
        self.reserve()
        with patch("app.routers.equipment.resolve_caller", side_effect=forbidden()):
            denied = self.client.post(
                "/equipment/reservations/reverification", headers=self.headers, json={"eventId": "e1"}
            )

        self.assertEqual(denied.status_code, 403)
        self.assertFalse(self.service.list_event_reservations("e1")[0].needsReverification)

    def test_technical_support_see_the_queue_and_can_reconfirm(self):
        reservation_id = self.reserve()
        self.service.flag_for_reverification("e1", "Quantity rose")

        with (
            patch("app.routers.equipment.resolve_caller", return_value=CALLER),
            patch("app.services.equipment_service._event_record", return_value={}),
            patch("app.services.equipment_service._settle_reverification"),
        ):
            queue = self.client.get("/equipment/queue", headers=self.headers)
            saved = self.client.post(f"/equipment/reservations/{reservation_id}/reconfirm", headers=self.headers)

        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.json()[0]["reservationId"], reservation_id)
        self.assertEqual(saved.status_code, 200)
        self.assertFalse(saved.json()["needsReverification"])
        self.assertEqual(saved.json()["quantity"], 1)


class TestReservationReconfirm(ReverificationCase):
    def test_reconfirm_clears_the_flag_without_raising_the_quantity(self):
        reservation_id = self.reserve(quantity=1)
        self.service.flag_for_reverification("e1", "Equipment requirements changed")

        saved = self.service.reconfirm_reservation(reservation_id)

        self.assertFalse(saved.needsReverification)
        self.assertEqual(saved.quantity, 1)
        self.assertEqual(saved.status, "active")
        self.assertEqual(self.service.reverification_queue(), [])

    def test_unavailable_extra_units_stay_flagged_and_are_not_reserved(self):
        reservation_id = self.reserve(quantity=1)
        self.service.flag_for_reverification("e1", "Quantity rose")
        event = {"equipmentLines": [{"equipmentId": self.equipment_id, "quantity": 40}]}

        with patch("app.services.equipment_service._event_record", return_value=event):
            with self.assertRaises(HTTPException) as raised:
                self.service.reconfirm_reservation(reservation_id, "Bearer token")

        kept = self.service.get_reservation(reservation_id)
        self.assertIn("unavailable", str(raised.exception.detail))
        self.assertTrue(kept.needsReverification)
        self.assertEqual(kept.quantity, 1)
        self.assertEqual(len(self.service.reverification_queue()), 1)

    def test_a_reservation_that_is_not_flagged_cannot_be_reconfirmed(self):
        reservation_id = self.reserve()
        with self.assertRaises(HTTPException):
            self.service.reconfirm_reservation(reservation_id)

    def test_notices_and_settling_are_best_effort(self):
        from app.services.equipment_service import _notify_role, _settle_reverification

        users = patch("app.services.equipment_service.httpx.get")
        posted = patch("app.services.equipment_service.httpx.post")
        with users as get, posted as post:
            get.return_value.status_code = 200
            get.return_value.json.return_value = [
                {"userId": "u4", "email": "tia@x.com", "role": "techsupport"},
                {"userId": "u9", "email": "other@x.com", "role": "venue"},
            ]
            post.return_value.status_code = 201
            _notify_role("techsupport", "e1", "Equipment needs re-verification", "Check it", "Bearer token", "equipment.reverification")
            _settle_reverification("e1", "Bearer token")
            get.return_value.status_code = 503
            _notify_role("techsupport", "e1", "Equipment needs re-verification", "Check it", "Bearer token", "equipment.reverification")
            post.side_effect = __import__("httpx").ConnectError("down")
            _settle_reverification("e1", "Bearer token")
            get.return_value.status_code = 200
            _notify_role("techsupport", "e1", "Equipment needs re-verification", "Check it", "Bearer token", "equipment.reverification")
