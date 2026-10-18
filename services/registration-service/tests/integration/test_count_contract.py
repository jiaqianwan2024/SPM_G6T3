"""Provider side of the registration-count contract.

event-service reads `GET /registrations/count?eventId=...` and expects `{"count": <int>}`.
The agreed shape lives in shared/testing/contracts/registration_count.json; event-service's
test_registration_count_contract.py checks its client against the same file. If either
side changes the shape, one of the two tests fails.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.models.attendee_registration import AttendeeRegistration
from app.models.registration_window import RegistrationWindow
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase

CONTRACT = json.loads(
    (Path(__file__).resolve().parents[4] / "shared/testing/contracts/registration_count.json").read_text()
)


class TestRegistrationCountContract(ServiceTestCase):
    def test_count_answers_with_the_agreed_shape(self):
        now = datetime.utcnow()
        event_id = CONTRACT["request"]["query"]["eventId"]
        self.db.add(RegistrationWindow(eventId=event_id, capacity=5, opensAt=now, closesAt=now + timedelta(days=1)))
        for i in range(CONTRACT["response"]["body"]["count"]):
            self.db.add(
                AttendeeRegistration(
                    attendeeRegistrationId=f"r{i}", eventId=event_id, attendeeName=f"A{i}",
                    attendeeEmail=f"a{i}@example.com", status="registered",
                )
            )
        self.db.add(  # a withdrawn row must not be counted
            AttendeeRegistration(
                attendeeRegistrationId="gone", eventId=event_id, attendeeName="Gone",
                attendeeEmail="gone@example.com", status="withdrawn",
            )
        )
        self.db.commit()

        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.addCleanup(app.dependency_overrides.clear)
        with TestClient(app) as client:
            resp = client.request(
                CONTRACT["request"]["method"], CONTRACT["request"]["path"], params=CONTRACT["request"]["query"]
            )

        self.assertEqual(resp.status_code, CONTRACT["response"]["status"])
        self.assertEqual(resp.json(), CONTRACT["response"]["body"])
