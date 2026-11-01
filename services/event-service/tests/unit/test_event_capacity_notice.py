from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from tests.unit.support import EventCase, insert_event


class TestCapacityNotice(EventCase):
    """SPM-11 AC9: the organiser and the assigned coordinator hear when registration fills up."""

    def full_event(self, **overrides):
        data = dict(
            eventId="e-full", eventName="Summit", coordinatorId="coord-1", registrationEnabled=True, capacity=3
        )
        data.update(overrides)
        return insert_event(self.db, **data)

    def test_a_full_event_tells_the_organiser_and_coordinator_once_per_capacity(self):
        self.full_event()  # EventCase counts 3 registrations.

        result = self.service.notify_capacity_reached("e-full", "Bearer t")

        self.assertEqual(result, {"eventId": "e-full", "notified": True})
        trigger, event_id, occurrence, recipients, context = self.published.call_args.args
        self.assertEqual((trigger, event_id, occurrence), ("registration.full", "e-full", "e-full:registration.full:3"))
        self.assertEqual(
            recipients, [{"userId": "org-1", "role": "organiser"}, {"userId": "coord-1", "role": "coordinator"}]
        )
        self.assertEqual(context, {"eventName": "Summit", "capacity": "3"})

    def test_places_still_left_tell_nobody(self):
        self.full_event(capacity=4)

        self.assertEqual(self.service.notify_capacity_reached("e-full", None)["notified"], False)
        self.published.assert_not_called()

    def test_an_event_without_registration_or_capacity_tells_nobody(self):
        self.full_event(eventId="e-off", registrationEnabled=False)
        self.full_event(eventId="e-zero", capacity=0)

        self.assertFalse(self.service.notify_capacity_reached("e-off", None)["notified"])
        self.assertFalse(self.service.notify_capacity_reached("e-zero", None)["notified"])
        self.published.assert_not_called()


class TestCapacityNoticeRoute(EventCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.event.resolve_caller", return_value={"userId": "att-1", "role": "attendee"})
        self.caller.start()
        self.client = TestClient(app)

    def tearDown(self):
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_the_attendee_who_took_the_last_place_can_raise_it(self):
        insert_event(self.db, eventId="e-full", registrationEnabled=True, capacity=3)

        response = self.client.post("/events/e-full/capacity-notice", headers={"Authorization": "Bearer t"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"eventId": "e-full", "notified": True})
