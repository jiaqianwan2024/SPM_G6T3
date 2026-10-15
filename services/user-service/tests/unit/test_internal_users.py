from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from shared.testing.cases import ServiceTestCase
from tests.unit.support import seed_user

KEY = {"X-Service-Key": "key-1"}


class TestInternalUsers(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.key = patch.object(settings, "internal_service_key", "key-1")
        self.key.start()
        self.client = TestClient(app)
        self.client.__enter__()
        seed_user(self.db, userId="u-venue", email="v@connectsphere.com", role="venue")
        seed_user(self.db, userId="u-tech", email="t@connectsphere.com", role="techsupport")
        seed_user(self.db, userId="u-org", email="o@connectsphere.com", role="organiser")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.key.stop()
        super().tearDown()

    def test_it_returns_only_the_id_and_role_of_users_holding_the_asked_roles(self):
        response = self.client.get("/internal/users", params={"roles": "venue, techsupport"}, headers=KEY)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(response.json(), key=lambda row: row["userId"]),
            [{"userId": "u-tech", "role": "techsupport"}, {"userId": "u-venue", "role": "venue"}],
        )

    def test_it_needs_the_service_key_and_no_user_token(self):
        self.assertEqual(self.client.get("/internal/users", params={"roles": "venue"}).status_code, 403)
        wrong = self.client.get("/internal/users", params={"roles": "venue"}, headers={"X-Service-Key": "nope"})
        self.assertEqual(wrong.status_code, 403)
