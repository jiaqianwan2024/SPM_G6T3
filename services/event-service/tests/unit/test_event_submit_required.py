from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import ORGANISER

HEADERS = {"Authorization": "Bearer token"}
DETAILS = {
    "eventName": "AUTO-SPM14",
    "category": "Conference",
    "purpose": "Share",
    "proposedStartAt": "2026-11-01T09:00:00",
    "proposedEndAt": "2026-11-01T17:00:00",
    "expectedAttendance": 10,
    "registrationEnabled": False,
}


class TestSubmitNeedsEveryRequiredField(ServiceTestCase):
    """SPM-14 AC1 / SPM-82 AC1: name, category, purpose, dates, attendance of at least one and the
    registration answer are required to submit, and every missing one is listed."""

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.routers.event.current_organiser", return_value=ORGANISER),
            patch("app.routers.event.resolve_caller", return_value=ORGANISER),
        ]
        for p in self.patches:
            p.start()
        self.client = TestClient(app)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def missing(self, response):
        self.assertEqual(response.status_code, 422, response.text)
        return sorted(error["loc"][-1] for error in response.json()["detail"])

    def test_a_request_missing_category_purpose_and_attendance_lists_all_three(self):
        body = {key: value for key, value in DETAILS.items() if key not in ("category", "purpose", "expectedAttendance")}

        response = self.client.post("/events", headers=HEADERS, json=body)

        self.assertEqual(self.missing(response), ["category", "expectedAttendance", "purpose"])

    def test_a_blank_category_or_purpose_is_missing(self):
        response = self.client.post("/events", headers=HEADERS, json={**DETAILS, "category": "  ", "purpose": ""})

        self.assertEqual(self.missing(response), ["category", "purpose"])

    def test_a_complete_request_is_submitted(self):
        response = self.client.post("/events", headers=HEADERS, json=DETAILS)

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual((response.json()["status"], response.json()["category"]), ("submitted", "Conference"))

    def test_a_category_in_another_case_is_stored_as_the_form_spells_it(self):
        response = self.client.post("/events", headers=HEADERS, json={**DETAILS, "category": " meeting "})

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["category"], "Meeting")

    def test_a_category_outside_the_list_is_refused(self):
        response = self.client.post("/events", headers=HEADERS, json={**DETAILS, "category": "Seminar"})

        self.assertEqual(self.missing(response), ["category"])
        self.assertIn("Conference, Workshop, Networking, Meeting", response.text)

    def test_a_draft_with_a_category_outside_the_list_is_refused(self):
        response = self.client.post("/events/drafts", headers=HEADERS, json={"eventName": "AUTO-SPM82", "category": "party"})

        self.assertEqual(self.missing(response), ["category"])

    def test_a_draft_submitted_with_its_details_needs_the_same_fields(self):
        draft = self.client.post("/events/drafts", headers=HEADERS, json={"eventName": "AUTO-SPM82"}).json()
        body = {key: value for key, value in DETAILS.items() if key != "purpose"}

        response = self.client.post(f"/events/{draft['eventId']}/submit", headers=HEADERS, json=body)

        self.assertEqual(self.missing(response), ["purpose"])

    def test_a_saved_draft_without_category_or_purpose_is_not_submitted(self):
        draft = self.client.post("/events/drafts", headers=HEADERS, json={"eventName": "AUTO-SPM82"}).json()
        dates = {key: DETAILS[key] for key in ("proposedStartAt", "proposedEndAt", "expectedAttendance")}
        self.client.patch(f"/events/{draft['eventId']}", headers=HEADERS, json=dates)

        response = self.client.post(f"/events/{draft['eventId']}/submit", headers=HEADERS)

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Missing category, purpose")
