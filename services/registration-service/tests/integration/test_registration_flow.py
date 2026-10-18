"""Registration lifecycle over HTTP and SQL, with the other services faked.

Real:    FastAPI routes, RegistrationService, DAOs, SQLAlchemy, httpx request building
         and response parsing.
Doubles: the services this one calls over HTTP (event, notification). `FakePlatform`
         answers at the httpx transport, so URLs, headers and JSON bodies are still
         exercised. Identity is a plain caller dict. The database is a fresh SQLite
         file per test (ServiceTestCase).

Each test asserts on stored rows and responses (state). A notification is asserted
only where it is part of the requirement (a withdrawal tells the attendee).
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.models.attendee_registration import AttendeeRegistration
from app.models.registration_window import RegistrationWindow
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase

AMY = {"userId": "u-amy", "role": "attendee", "email": "amy@example.com"}
BEN = {"userId": "u-ben", "role": "attendee", "email": "ben@example.com"}
ORGANISER = {"userId": "u-org", "role": "organiser", "email": "org@example.com"}
HEADERS = {"Authorization": "Bearer token"}

# Patching `httpx.Client` through a module replaces the one global attribute, so keep
# the real class for the fakes to build on.
REAL_CLIENT = httpx.Client


def make_event(**overrides):
    """A confirmed, open-for-registration event that starts in a week."""
    now = datetime.utcnow()
    event = {
        "eventId": "e1",
        "eventName": "Summit",
        "status": "confirmed",
        "category": "conference",
        "capacity": 2,
        "registrationEnabled": True,
        "registrationOpensAt": (now - timedelta(days=1)).isoformat(),
        "registrationClosesAt": (now + timedelta(days=3)).isoformat(),
        "proposedStartAt": (now + timedelta(days=7)).isoformat(),
        "proposedEndAt": (now + timedelta(days=7, hours=8)).isoformat(),
    }
    event.update(overrides)
    return event


class FakePlatform:
    """In-memory event-service and notification-service, reached through httpx."""

    def __init__(self, event):
        self.event = event
        self.down = False
        self.sent = []  # (method, path, json body)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("event-service is down", request=request)
        path = request.url.path
        if request.method == "POST":
            self.sent.append((request.method, path, request.read().decode()))
            return httpx.Response(201 if path.endswith("/records") else 200, json={})
        if path == f"/events/{self.event['eventId']}":
            return httpx.Response(200, json=self.event)
        if path.endswith("/registration-access"):
            return httpx.Response(200, json=self.event)
        if path.endswith("/attendee-card"):
            return httpx.Response(200, json=self.event)
        return httpx.Response(404, json={"detail": "not found"})

    def client_factory(self):
        transport = httpx.MockTransport(self.handle)
        return lambda *args, **kwargs: REAL_CLIENT(transport=transport, **kwargs)

    def get(self, url, headers=None, timeout=None, params=None):
        with REAL_CLIENT(transport=httpx.MockTransport(self.handle)) as client:
            return client.get(url, headers=headers, params=params)


class RegistrationFlowCase(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.platform = FakePlatform(make_event())
        self.caller = dict(AMY)

        # Patch where the names are looked up (registration_service / registration router).
        patches = [
            patch("app.services.registration_service.httpx.Client", self.platform.client_factory()),
            patch("app.routers.registration.httpx.get", self.platform.get),
            patch("app.routers.registration.resolve_caller", side_effect=lambda *_a, **_k: self.caller),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

        self.open_window("e1", capacity=2)

    # ---- test data helpers: only what matters is visible in the test --------
    def open_window(self, event_id, capacity):
        now = datetime.utcnow()
        self.db.add(
            RegistrationWindow(
                eventId=event_id,
                capacity=capacity,
                opensAt=now - timedelta(days=1),
                closesAt=now + timedelta(days=3),
            )
        )
        self.db.commit()

    def register(self, name="Amy", email="amy@example.com", event_id="e1"):
        return self.client.post(
            "/registrations", headers=HEADERS, json={"eventId": event_id, "name": name, "email": email}
        )

    def rows(self, event_id="e1"):
        self.db.expire_all()
        return self.db.query(AttendeeRegistration).filter_by(eventId=event_id).all()

    def count(self, event_id="e1"):
        return self.client.get("/registrations/count", params={"eventId": event_id}).json()["count"]


class TestRegistering(RegistrationFlowCase):
    def test_register_is_stored_counted_and_listed_with_event_details(self):
        resp = self.register()

        self.assertEqual(resp.status_code, 201)
        stored = self.rows()
        self.assertEqual([(r.attendeeEmail, r.status, r.userId) for r in stored], [("amy@example.com", "registered", "u-amy")])
        self.assertEqual(self.count(), 1)

        mine = self.client.get("/registrations/me", headers=HEADERS)
        self.assertEqual(mine.status_code, 200)
        self.assertEqual([r["eventName"] for r in mine.json()], ["Summit"])  # enriched from event-service

    def test_same_email_cannot_register_twice_even_in_different_case(self):
        self.register()

        resp = self.register(email="AMY@example.com")

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(len(self.rows()), 1)

    def test_full_event_refuses_the_next_attendee_and_stores_nothing(self):
        self.register(name="Amy", email="amy@example.com")
        self.register(name="Cat", email="cat@example.com")

        resp = self.register(name="Ben", email="ben@example.com")

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self.count(), 2)

    def test_unconfirmed_event_refuses_registration(self):
        self.platform.event = make_event(status="submitted")

        resp = self.register()

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self.rows(), [])

    def test_closed_registration_window_refuses_registration(self):
        past = datetime.utcnow() - timedelta(hours=1)
        self.platform.event = make_event(registrationClosesAt=past.isoformat())

        resp = self.register()

        self.assertEqual(resp.status_code, 409)
        self.assertEqual(self.rows(), [])

    def test_event_service_outage_is_reported_and_nothing_is_stored(self):
        self.platform.down = True

        resp = self.register()

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(self.rows(), [])


class TestWithdrawing(RegistrationFlowCase):
    def test_withdrawal_keeps_the_row_releases_the_place_and_tells_the_attendee(self):
        registration_id = self.register().json()["attendeeRegistrationId"]

        resp = self.client.post(f"/registrations/{registration_id}/withdraw", headers=HEADERS)

        self.assertEqual(resp.status_code, 200)
        (row,) = self.rows()
        self.assertEqual(row.status, "withdrawn")
        self.assertIsNotNone(row.withdrawnAt)
        self.assertEqual(self.count(), 0)
        paths = [path for _method, path, _body in self.platform.sent]
        self.assertIn("/notifications/records", paths)
        self.assertIn("/notifications", paths)

    def test_a_released_place_can_be_taken_by_someone_else(self):
        self.open_window("e2", capacity=1)
        self.platform.event = make_event(eventId="e2", capacity=1)
        first = self.register(event_id="e2").json()["attendeeRegistrationId"]
        self.client.post(f"/registrations/{first}/withdraw", headers=HEADERS)
        self.caller = dict(BEN)

        resp = self.register(name="Ben", email="ben@example.com", event_id="e2")

        self.assertEqual(resp.status_code, 201)
        self.assertEqual(
            sorted((r.attendeeEmail, r.status) for r in self.rows("e2")),
            [("amy@example.com", "withdrawn"), ("ben@example.com", "registered")],
        )

    def test_someone_elses_registration_cannot_be_withdrawn(self):
        registration_id = self.register().json()["attendeeRegistrationId"]
        self.caller = dict(BEN)

        resp = self.client.post(f"/registrations/{registration_id}/withdraw", headers=HEADERS)

        self.assertEqual(resp.status_code, 403)
        self.assertEqual([r.status for r in self.rows()], ["registered"])

    def test_withdrawing_twice_is_a_conflict(self):
        registration_id = self.register().json()["attendeeRegistrationId"]
        self.client.post(f"/registrations/{registration_id}/withdraw", headers=HEADERS)

        resp = self.client.post(f"/registrations/{registration_id}/withdraw", headers=HEADERS)

        self.assertEqual(resp.status_code, 409)

    def test_withdrawal_is_closed_once_the_event_has_started(self):
        registration_id = self.register().json()["attendeeRegistrationId"]
        self.platform.event = make_event(proposedStartAt=(datetime.utcnow() - timedelta(minutes=1)).isoformat())

        resp = self.client.post(f"/registrations/{registration_id}/withdraw", headers=HEADERS)

        self.assertEqual(resp.status_code, 409)
        self.assertEqual([r.status for r in self.rows()], ["registered"])

    def test_withdrawal_is_closed_for_a_cancelled_event(self):
        registration_id = self.register().json()["attendeeRegistrationId"]
        self.platform.event = make_event(status="cancelled")

        resp = self.client.post(f"/registrations/{registration_id}/withdraw", headers=HEADERS)

        self.assertEqual(resp.status_code, 409)
        self.assertEqual([r.status for r in self.rows()], ["registered"])


class TestRoster(RegistrationFlowCase):
    def test_attendee_sees_places_left_but_not_other_attendees(self):
        self.register()
        self.caller = dict(BEN)

        resp = self.client.get("/registrations", params={"eventId": "e1"}, headers=HEADERS)

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual((body["registered"], body["remaining"]), (1, 1))
        self.assertEqual(body["attendees"], [])

    def test_organiser_sees_names_and_withdrawn_rows_can_be_left_out(self):
        withdrawn = self.register(name="Amy", email="amy@example.com").json()["attendeeRegistrationId"]
        self.register(name="Cat", email="cat@example.com")
        self.client.post(f"/registrations/{withdrawn}/withdraw", headers=HEADERS)
        self.caller = dict(ORGANISER)

        everyone = self.client.get("/registrations", params={"eventId": "e1"}, headers=HEADERS).json()
        current = self.client.get(
            "/registrations", params={"eventId": "e1", "includeWithdrawn": "false"}, headers=HEADERS
        ).json()

        self.assertEqual(sorted(a["attendeeName"] for a in everyone["attendees"]), ["Amy", "Cat"])
        self.assertEqual((everyone["registered"], everyone["withdrawn"]), (1, 1))
        self.assertEqual([a["attendeeName"] for a in current["attendees"]], ["Cat"])

    def test_registrations_require_a_signed_in_user(self):
        app.dependency_overrides.pop(require_authenticated_user)

        resp = self.client.get("/registrations/mine")

        self.assertEqual(resp.status_code, 401)
