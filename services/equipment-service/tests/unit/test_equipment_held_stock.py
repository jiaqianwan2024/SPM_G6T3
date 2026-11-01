"""Every reservation that holds units counts against availability, and none can take more than is free."""

from fastapi import HTTPException

from app.schemas.equipment import EquipmentQuantityReserve, EquipmentRequestCreate, RestoredReservation
from tests.unit.support import CALLER, COORDINATOR, END, START, EquipmentCase, equipment_create


class TestHeldStock(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.projector = self.service.create_equipment(equipment_create(code="HOLD", totalQuantity=3), CALLER).equipmentId

    def reserve(self, event_id, quantity):
        return self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId=event_id, equipmentId=self.projector, quantity=quantity, startsAt=START, endsAt=END
            ),
            CALLER,
        )

    def request(self, event_id, quantity):
        return self.service.create_request(
            EquipmentRequestCreate(
                eventId=event_id, equipmentId=self.projector, quantity=quantity, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )

    def refused(self, call, *args) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            call(*args)
        self.assertEqual(ctx.exception.status_code, 409)
        return ctx.exception

    def test_raising_a_reservation_takes_only_what_is_free(self):
        # 3 owned: e1 holds 1 and e2 holds 1, so e2 can grow to 2 and no further. The check used to add
        # e2's own units back a second time, letting it grow to 3 and book 4 of 3.
        self.reserve("e1", 1)
        held = self.reserve("e2", 1)

        self.assertEqual(self.service.adjust_reservation(held.reservationId, 2, CALLER).quantity, 2)
        refused = self.refused(self.service.adjust_reservation, held.reservationId, 3, CALLER)

        self.assertIn("Only 2 available", refused.detail)
        self.assertEqual(self.service.get_reservation(held.reservationId).quantity, 2)

    def test_a_partial_reservation_holds_its_units_until_it_is_released(self):
        request = self.request("e3", 4)
        self.service.record_partial(request.requestId, 2, "Only two free", CALLER, None)

        refused = self.refused(self.reserve, "e4", 2)
        self.assertIn("Only 1 available", refused.detail)

        released = self.service.release_holds_for_event("e3", CALLER, "The event was cancelled")
        self.assertEqual([row.previousStatus for row in released], ["partial"])
        self.assertEqual(self.reserve("e4", 2).quantity, 2)

    def test_one_partial_reservation_can_be_released_and_restored(self):
        request = self.request("e3", 4)
        self.service.record_partial(request.requestId, 2, "Only two free", CALLER, None)
        (partial,) = self.service.list_event_reservations("e3")

        self.assertEqual(self.service.release_reservation(partial.reservationId, CALLER, "Not needed").status, "released")
        restored = self.service.restore_holds_for_event(
            "e3", [RestoredReservation(reservationId=partial.reservationId, status="partial")], CALLER
        )

        self.assertEqual([row.status for row in restored], ["partial"])

    def test_a_partial_is_recorded_once(self):
        request = self.request("e3", 4)
        self.service.record_partial(request.requestId, 1, "Only one free", CALLER, None)

        refused = self.refused(self.service.record_partial, request.requestId, 1, "Again", CALLER, None)

        self.assertIn("already partial", refused.detail)
        self.assertEqual(len(self.service.list_event_reservations("e3")), 1)

    def test_reserving_an_approved_request_checks_the_stock_again(self):
        # Approval holds nothing, so the units can go to another event before the reservation is made.
        request = self.request("e1", 2)
        stored = self.service.request_dao.get_by_id(request.requestId)
        stored.status = "approved"
        self.db.commit()
        self.reserve("e2", 2)

        refused = self.refused(self.service.reserve_request, request.requestId)

        self.assertIn("Only 1 available", refused.detail)
        self.assertEqual(self.service.list_event_reservations("e1"), [])
        self.assertEqual(self.service.get_request(request.requestId).status, "approved")
