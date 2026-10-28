import asyncio
import unittest
from contextlib import asynccontextmanager
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services import reminder_schedule
from app.services.reminder_schedule import (
    daily_reminders_lifespan,
    run_daily,
    run_reminders_once,
    seconds_until_midnight_sgt,
)
from tests.unit.support import EventCase


class TestSecondsUntilMidnight(unittest.TestCase):
    def test_the_wait_is_to_the_next_midnight_in_singapore(self):
        # 02:00 UTC is 10:00 in Singapore, so 14 hours to go.
        self.assertEqual(seconds_until_midnight_sgt(datetime(2026, 10, 28, 2, 0)), 14 * 3600)

    def test_the_singapore_date_decides_not_the_utc_date(self):
        # 16:30 UTC on the 28th is 00:30 on the 29th in Singapore, so the next midnight is the 30th.
        self.assertEqual(seconds_until_midnight_sgt(datetime(2026, 10, 28, 16, 30)), 23.5 * 3600)

    def test_exactly_midnight_waits_a_full_day(self):
        self.assertEqual(seconds_until_midnight_sgt(datetime(2026, 10, 28, 16, 0)), 24 * 3600)


class TestRunOnce(EventCase):
    def test_a_check_is_logged_and_the_session_closed(self):
        result = MagicMock(checked=3, reminded=[1])
        with patch.object(reminder_schedule, "EventReminders") as reminders:
            reminders.return_value.run.return_value = result
            run_reminders_once()

        reminders.return_value.run.assert_called_once_with()

    def test_a_failed_check_is_swallowed_so_the_schedule_keeps_going(self):
        with patch.object(reminder_schedule, "EventReminders", side_effect=RuntimeError("boom")):
            run_reminders_once()


class TestRunDaily(unittest.IsolatedAsyncioTestCase):
    async def test_it_runs_at_startup_then_after_each_wait_until_midnight(self):
        runs, waits = [], []

        async def sleep(seconds):
            waits.append(seconds)
            if len(waits) == 2:
                raise asyncio.CancelledError

        with self.assertRaises(asyncio.CancelledError):
            await run_daily(run=lambda: runs.append("run"), now=lambda: datetime(2026, 10, 28, 2, 0), sleep=sleep)

        self.assertEqual(runs, ["run", "run"])
        self.assertEqual(waits, [14 * 3600, 14 * 3600])


class TestLifespan(unittest.IsolatedAsyncioTestCase):
    def original(self, events):
        @asynccontextmanager
        async def lifespan(app):
            events.append("up")
            yield
            events.append("down")

        return lifespan

    async def test_the_daily_check_starts_with_the_service_and_stops_with_it(self):
        events = []
        started = asyncio.Event()

        async def fake_daily():
            started.set()
            await asyncio.sleep(3600)

        with patch.object(settings, "event_reminder_schedule_enabled", True), patch.object(
            reminder_schedule, "run_daily", fake_daily
        ):
            async with daily_reminders_lifespan(self.original(events))(None):
                await started.wait()
                events.append("running")

        self.assertEqual(events, ["up", "running", "down"])

    async def test_it_can_be_switched_off(self):
        events = []
        with patch.object(settings, "event_reminder_schedule_enabled", False), patch.object(
            reminder_schedule, "run_daily"
        ) as daily:
            async with daily_reminders_lifespan(self.original(events))(None):
                pass

        daily.assert_not_called()
        self.assertEqual(events, ["up", "down"])
