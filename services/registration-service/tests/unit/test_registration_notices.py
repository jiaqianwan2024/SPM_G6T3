from datetime import datetime, timedelta
from unittest.mock import patch

import httpx

from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.services.registration_service import RegistrationService
from shared.testing.cases import ServiceTestCase
from tests.unit.support import RecordingClient, confirmed_event, make_window


class FailingClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        raise httpx.ConnectError("service is down")

    def __exit__(self, *args):
        return False


class TestRegistrationWindowAndNotices(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.service = RegistrationService(
            self.db, AttendeeRegistrationDAO(self.db), RegistrationWindowDAO(self.db)
        )
        RecordingClient.calls = []

    def register(self, event, name="Amy Wong", email="amy@example.com", client=RecordingClient, user_id="u-amy"):
        with patch("app.services.registration_service._event", return_value=event):
            with patch("app.services.registration_service.httpx.Client", client):
                return self.service.register("e1", name, email, user_id=user_id, authorization="Bearer t")

    def posted(self, path):
        return [call for call in RecordingClient.calls if call["url"].endswith(path)]

    def test_an_existing_window_is_refreshed_from_the_event(self):
        # SPM-90 can change the capacity and period after the first registration.
        make_window(self.db, capacity=3)
        later = (datetime.utcnow() + timedelta(days=9)).replace(microsecond=0)

        self.register(confirmed_event(capacity=25, registrationClosesAt=later.isoformat()))

        window = RegistrationWindowDAO(self.db).get_for_event("e1")
        self.assertEqual(window.capacity, 25)
        self.assertEqual(window.closesAt, later)

    def test_the_places_are_counted_in_a_transaction_that_starts_at_the_lock(self):
        # SPM-11 AC7: under REPEATABLE READ a count in the transaction that first read the window
        # would miss a registration committed while waiting for the lock, so that one ends first.
        make_window(self.db)
        steps = []
        real_read, real_commit = self.service.window_dao.get_for_event, self.db.commit

        def read(event_id, lock=False):
            steps.append("locked read" if lock else "read")
            return real_read(event_id, lock=lock)

        def commit():
            steps.append("commit")
            return real_commit()

        with patch.object(self.service.window_dao, "get_for_event", side_effect=read), patch.object(
            self.db, "commit", side_effect=commit
        ):
            self.register(confirmed_event())

        self.assertEqual(steps[:3], ["read", "commit", "locked read"])

    def test_a_window_created_meanwhile_by_another_registration_is_used(self):
        # Both first registrations saw no window; this one loses the insert and locks the other's row.
        make_window(self.db)
        real = self.service.window_dao.get_for_event
        calls = []

        def none_then_real(event_id, lock=False):
            calls.append(lock)
            return None if len(calls) == 1 else real(event_id, lock=lock)

        with patch.object(self.service.window_dao, "get_for_event", side_effect=none_then_real):
            row = self.register(confirmed_event())

        self.assertEqual(row.status, "registered")
        self.assertEqual(calls, [False, True])

    def test_the_attendee_is_not_notified_of_their_own_registration(self):
        # SPM-93 AC5: the screen confirms it; no in-app notice or email is sent.
        self.register(confirmed_event())

        self.assertEqual(self.posted("/notifications/records"), [])
        self.assertEqual(self.posted("/notifications"), [])

    def test_a_capacity_notice_that_cannot_be_sent_does_not_undo_the_registration(self):
        with self.assertLogs("app.services.registration_service", level="WARNING") as logs:
            row = self.register(confirmed_event(capacity=1), client=FailingClient)

        self.assertEqual(row.status, "registered")
        self.assertEqual(len(self.service.list_for_event("e1")), 1)
        self.assertTrue(any("capacity notice for e1 could not be sent" in line for line in logs.output))

    def test_taking_the_last_place_asks_event_service_to_tell_the_organiser_and_coordinator(self):
        # SPM-11 AC9: event-service owns who the organiser and coordinator are.
        self.register(confirmed_event(capacity=2), email="amy@example.com")
        self.assertEqual(self.posted("/capacity-notice"), [])

        self.register(confirmed_event(capacity=2), name="Ben Tan", email="ben@example.com", user_id="u-ben")

        (notice,) = self.posted("/capacity-notice")
        self.assertTrue(notice["url"].endswith("/events/e1/capacity-notice"))
        self.assertEqual(notice["headers"], {"Authorization": "Bearer t"})
