from datetime import timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.equipment import (
    EquipmentAvailabilityIn,
    EquipmentQuantityReserve,
    ReservationReschedule,
    ReservationReschedulePreview,
)
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, COORDINATOR, END, START, EquipmentCase, equipment_create

NEW_START = START + timedelta(days=7)
NEW_END = END + timedelta(days=7)


class RescheduleCase(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.equipment_id = self.service.create_equipment(equipment_create(totalQuantity=5), CALLER).equipmentId

    def reserve(self, event_id="e1", quantity=1, start=START, end=END):
        return self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId=event_id, equipmentId=self.equipment_id, quantity=quantity, startsAt=start, endsAt=end
            ),
            CALLER,
        ).reservationId

    def preview(self, start=NEW_START, end=NEW_END):
        return self.service.preview_reschedule(ReservationReschedulePreview(eventId="e1", startsAt=start, endsAt=end))

    def apply(self, authorization=None):
        return self.service.reschedule_reservations(
            ReservationReschedule(eventId="e1", startsAt=NEW_START, endsAt=NEW_END, reason="Speaker moved"),
            COORDINATOR,
            authorization,
        )

    def free(self, start, end):
        return self.service.check_availability(
            EquipmentAvailabilityIn(equipmentId=self.equipment_id, startsAt=start, endsAt=end)
        ).availableQuantity


class TestPreview(RescheduleCase):
    """SPM-87 AC2 and AC5."""

    def test_each_reservation_is_judged_against_other_events_at_the_new_time(self):
        held = self.reserve(quantity=2)
        self.reserve("e2", quantity=4, start=NEW_START, end=NEW_END)

        [judged] = self.preview()

        self.assertEqual((judged.reservationId, judged.equipmentName, judged.quantity), (held, "Projector", 2))
        self.assertEqual((judged.availableQuantity, judged.canMeet, judged.shortfall, judged.outcome), (1, False, 1, None))
        self.assertEqual(self.service.get_reservation(held).startsAt, START)

    def test_the_events_own_reservations_never_stand_in_its_way(self):
        self.reserve(quantity=5)

        [judged] = self.preview(start=START + timedelta(hours=1), end=END + timedelta(hours=1))

        self.assertTrue(judged.canMeet)

    def test_reservations_of_the_same_equipment_share_what_is_free(self):
        self.reserve(quantity=2)
        self.reserve(quantity=2)
        self.reserve("e2", quantity=2, start=NEW_START, end=NEW_END)

        first, second = self.preview()

        self.assertEqual((first.availableQuantity, first.canMeet), (3, True))
        self.assertEqual((second.availableQuantity, second.canMeet, second.shortfall), (1, False, 1))

    def test_released_reservations_are_left_out_and_a_backwards_period_is_refused(self):
        released = self.reserve()
        self.service.release_reservation(released, CALLER)

        self.assertEqual(self.preview(), [])
        with self.assertRaises(HTTPException) as backwards:
            self.preview(start=NEW_END, end=NEW_START)
        self.assertEqual(backwards.exception.status_code, 422)


class TestApply(RescheduleCase):
    """SPM-87 AC5 and AC6."""

    def test_reservations_move_and_the_old_time_is_freed(self):
        held = self.reserve(quantity=3)
        self.assertEqual(self.free(START, END), 2)

        [moved] = self.apply()

        self.assertEqual((moved.outcome, moved.needsReverification), ("moved", False))
        stored = self.service.get_reservation(held)
        self.assertEqual((stored.startsAt, stored.endsAt, stored.status), (NEW_START, NEW_END, "active"))
        self.assertEqual(self.free(START, END), 5)
        self.assertEqual(self.free(NEW_START, NEW_END), 2)

    def test_one_that_cannot_be_met_is_flagged_not_dropped(self):
        held = self.reserve(quantity=2)
        self.reserve("e2", quantity=4, start=NEW_START, end=NEW_END)

        with patch("app.services.equipment_service._notify_role") as notify:
            [flagged] = self.apply(authorization="Bearer token")

        stored = self.service.get_reservation(held)
        self.assertEqual((flagged.outcome, flagged.shortfall), ("flagged", 1))
        self.assertEqual((stored.status, stored.quantity, stored.startsAt), ("active", 2, NEW_START))
        self.assertTrue(stored.needsReverification)
        self.assertEqual(
            stored.reverificationNote,
            "Event rescheduled. Speaker moved. Only 1 of 2 Projector are free at the new time.",
        )
        role, event_id, title, body = notify.call_args.args[:4]
        self.assertEqual((role, event_id), ("techsupport", "e1"))
        self.assertIn("2 × Projector (short by 1)", body)

    def test_technical_support_are_not_told_when_everything_is_met(self):
        self.reserve()

        with patch("app.services.equipment_service._notify_role") as notify:
            self.apply(authorization="Bearer token")

        notify.assert_not_called()

    def test_the_events_open_requests_take_the_new_time_and_other_events_stay(self):
        self.reserve()
        other = self.reserve("e2", start=START + timedelta(days=1), end=END + timedelta(days=1))

        self.apply()

        times = {(row.eventId, row.startsAt) for row in self.service.list_requests()}
        self.assertIn(("e1", NEW_START), times)
        self.assertNotIn(("e1", START), times)
        self.assertEqual(self.service.get_reservation(other).startsAt, START + timedelta(days=1))


class TestRescheduleRoutes(RescheduleCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}
        self.body = {"eventId": "e1", "startsAt": NEW_START.isoformat(), "endsAt": NEW_END.isoformat()}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, path, caller, coordinator="u-coord", body=None):
        with patch("app.routers.equipment.resolve_caller", return_value=caller), patch(
            "app.routers.equipment.fetch_event_coordinator", return_value=coordinator
        ), patch("app.services.equipment_service._notify_role"):
            return self.client.post(path, headers=self.headers, json=body or self.body)

    def test_the_assigned_coordinator_previews_and_applies(self):
        held = self.reserve()

        preview = self.post("/equipment/reservations/reschedule/preview", COORDINATOR)
        applied = self.post("/equipment/reservations/reschedule", COORDINATOR, body={**self.body, "reason": "x"})

        self.assertEqual((preview.status_code, preview.json()[0]["canMeet"]), (200, True))
        self.assertEqual((applied.status_code, applied.json()[0]["outcome"]), (200, "moved"))
        self.assertEqual(self.service.get_reservation(held).startsAt, NEW_START)

    def test_another_coordinator_is_refused(self):
        held = self.reserve()

        preview = self.post("/equipment/reservations/reschedule/preview", COORDINATOR, coordinator="u-other")
        applied = self.post("/equipment/reservations/reschedule", COORDINATOR, coordinator="u-other")

        self.assertEqual((preview.status_code, applied.status_code), (403, 403))
        self.assertEqual(self.service.get_reservation(held).startsAt, START)

    def test_only_coordinators_get_past_the_role_check(self):
        with patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR) as caller, patch(
            "app.routers.equipment.fetch_event_coordinator", return_value="u-coord"
        ):
            self.client.post("/equipment/reservations/reschedule/preview", headers=self.headers, json=self.body)

        self.assertEqual(caller.call_args.kwargs["allowed_roles"], {"coordinator"})
