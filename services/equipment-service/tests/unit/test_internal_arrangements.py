from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.schemas.equipment import EquipmentRequestCreate
from tests.unit.support import CALLER, END, START, EquipmentCase, equipment_create


class TestInternalArrangements(EquipmentCase):
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

    def request_for(self, event_id, equipment_id):
        return self.service.create_request(
            EquipmentRequestCreate(eventId=event_id, equipmentId=equipment_id, quantity=1, startsAt=START, endsAt=END),
            "u-coord",
        )

    def test_a_service_reads_one_events_requests_and_reservations_without_a_user_token(self):
        created = self.service.create_equipment(equipment_create(code="ARR"), CALLER)
        mine = self.request_for("e1", created.equipmentId)
        self.request_for("e2", created.equipmentId)
        self.service.review_request(mine.requestId, "u-tech", True, "OK")
        self.service.reserve_request(mine.requestId)

        response = self.client.get(
            "/internal/equipment/events/e1/arrangements", headers={"X-Service-Key": "key-1"}
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual([row["eventId"] for row in body["requests"]], ["e1"])
        self.assertEqual([row["eventId"] for row in body["reservations"]], ["e1"])

    def test_it_needs_the_service_key(self):
        response = self.client.get("/internal/equipment/events/e1/arrangements")

        self.assertEqual(response.status_code, 403)
