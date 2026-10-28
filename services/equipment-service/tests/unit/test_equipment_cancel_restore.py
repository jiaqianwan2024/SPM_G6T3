"""SPM-88: an event's equipment release names what it freed and who handled it, and can be undone."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.equipment_request import EquipmentRequest
from app.models.equipment_reservation import EquipmentReservation
from app.schemas.equipment import RestoredReservation
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden
from tests.unit.support import CALLER, COORDINATOR, END, START, EquipmentCase, equipment_create

HEADERS = {"Authorization": "Bearer token"}
ORGANISER = {"userId": "u-org", "role": "organiser", "organisationId": "org-1"}


class RestoreCase(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.projector = self.service.create_equipment(equipment_create(code="PX"), CALLER).equipmentId

    def reservation(self, reservation_id, event_id="e1", status="active", reviewed_by="u-tech"):
        request_id = f"req-{reservation_id}"
        self.db.add(
            EquipmentRequest(
                requestId=request_id, eventId=event_id, equipmentId=self.projector, quantity=1,
                technicalRequirements="", requestedBy="u-coord", status="reserved", startsAt=START, endsAt=END,
                reviewedBy=reviewed_by,
            )
        )
        self.db.add(
            EquipmentReservation(
                reservationId=reservation_id, requestId=request_id, eventId=event_id, equipmentId=self.projector,
                quantity=1, startsAt=START, endsAt=END, status=status,
            )
        )
        self.db.commit()
        return reservation_id

    def status(self, reservation_id):
        self.db.expire_all()
        return self.db.get(EquipmentReservation, reservation_id).status


class TestRelease(RestoreCase):
    def test_each_released_reservation_says_what_it_was_and_who_handled_it(self):
        self.reservation("active-one", status="active", reviewed_by="u-tia")
        self.reservation("reserved-one", status="reserved", reviewed_by="u-tom")

        released = self.service.release_holds_for_event("e1", COORDINATOR, "Cancelled")

        self.assertEqual(
            {row.reservationId: (row.status, row.previousStatus, row.handledBy) for row in released},
            {
                "active-one": ("released", "active", "u-tia"),
                "reserved-one": ("released", "reserved", "u-tom"),
            },
        )


class TestRestore(RestoreCase):
    def test_each_reservation_holds_its_stock_again_and_the_undo_is_logged(self):
        self.reservation("a", status="active")
        self.reservation("b", status="reserved")
        released = self.service.release_holds_for_event("e1", COORDINATOR, "Cancelled")

        restored = self.service.restore_holds_for_event(
            "e1",
            [RestoredReservation(reservationId=row.reservationId, status=row.previousStatus) for row in released],
            COORDINATOR,
        )

        self.assertEqual({row.reservationId for row in restored}, {"a", "b"})
        self.assertEqual((self.status("a"), self.status("b")), ("active", "reserved"))
        actions = [row.action for row in self.service.log_dao.list_for_equipment(self.projector)]
        self.assertEqual(actions.count("restore"), 2)

    def test_another_events_reservation_a_live_one_or_an_unknown_one_is_left_alone(self):
        self.reservation("theirs", event_id="e2", status="released")
        self.reservation("live", status="active")

        restored = self.service.restore_holds_for_event(
            "e1",
            [
                RestoredReservation(reservationId="theirs", status="active"),
                RestoredReservation(reservationId="live", status="reserved"),
                RestoredReservation(reservationId="missing", status="active"),
            ],
            COORDINATOR,
        )

        self.assertEqual(restored, [])
        self.assertEqual((self.status("theirs"), self.status("live")), ("released", "active"))


class TestReleaseRoutes(RestoreCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, path, caller, body, access=None):
        with patch("app.routers.equipment.resolve_caller", return_value=caller), patch(
            "app.routers.equipment.check_event_access", side_effect=access
        ) as checked:
            return self.client.post(path, headers=HEADERS, json=body), checked

    def test_the_events_own_organiser_can_release_and_restore_after_event_service_agrees(self):
        self.reservation("held")

        released, checked = self.post(
            "/equipment/reservations/release-for-event", ORGANISER, {"eventId": "e1", "reason": "Cancelled"}
        )
        self.assertEqual([(row["reservationId"], row["previousStatus"]) for row in released.json()], [("held", "active")])
        checked.assert_called_once_with("e1", HEADERS["Authorization"])

        restored, _ = self.post(
            "/equipment/reservations/restore-for-event",
            ORGANISER,
            {"eventId": "e1", "reservations": [{"reservationId": "held", "status": "active"}]},
        )
        self.assertEqual((restored.status_code, self.status("held")), (200, "active"))

    def test_another_organisations_organiser_is_refused_and_nothing_is_released(self):
        self.reservation("held")

        response, _ = self.post(
            "/equipment/reservations/release-for-event",
            ORGANISER,
            {"eventId": "e1"},
            access=forbidden("You can only open your own organisation's events."),
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.status("held"), "active")

    def test_a_coordinator_needs_no_event_check(self):
        self.reservation("held")

        response, checked = self.post("/equipment/reservations/release-for-event", COORDINATOR, {"eventId": "e1"})

        self.assertEqual(response.status_code, 200)
        checked.assert_not_called()
