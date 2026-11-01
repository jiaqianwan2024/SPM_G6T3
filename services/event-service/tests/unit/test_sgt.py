import unittest
from datetime import datetime, timedelta, timezone

from app.core.sgt import before_today, to_sgt


class TestToSgt(unittest.TestCase):
    """Stored times are naive UTC; people read them in Singapore time (UTC+8)."""

    def test_a_naive_utc_time_is_read_eight_hours_later(self):
        self.assertEqual(to_sgt(datetime(2030, 1, 7, 2, 0)), datetime(2030, 1, 7, 10, 0))

    def test_late_utc_evening_is_the_next_singapore_day(self):
        self.assertEqual(to_sgt(datetime(2030, 1, 6, 16, 0)), datetime(2030, 1, 7, 0, 0))
        self.assertEqual(to_sgt(datetime(2030, 1, 6, 15, 59)), datetime(2030, 1, 6, 23, 59))

    def test_a_time_with_an_offset_is_converted_from_that_offset(self):
        tokyo = timezone(timedelta(hours=9))
        self.assertEqual(to_sgt(datetime(2030, 1, 7, 11, 0, tzinfo=tokyo)), datetime(2030, 1, 7, 10, 0))
        self.assertEqual(to_sgt(datetime(2030, 1, 7, 2, 0, tzinfo=timezone.utc)), datetime(2030, 1, 7, 10, 0))


class TestBeforeToday(unittest.TestCase):
    """SPM-71 AC8 and SPM-5 AC10: a date before today, where today is the Singapore day."""

    NOW = datetime(2030, 1, 7, 2, 0)  # 10:00 on 7 Jan in Singapore

    def test_singapore_midnight_starts_today(self):
        # 7 Jan 00:00 in Singapore is 6 Jan 16:00 UTC.
        self.assertFalse(before_today(datetime(2030, 1, 6, 16, 0), self.NOW))
        self.assertTrue(before_today(datetime(2030, 1, 6, 15, 59), self.NOW))

    def test_earlier_today_and_later_days_are_not_before_today(self):
        self.assertFalse(before_today(datetime(2030, 1, 7, 0, 0), self.NOW))
        self.assertFalse(before_today(datetime(2031, 1, 1), self.NOW))

    def test_a_time_with_an_offset_is_compared_on_its_singapore_day(self):
        self.assertTrue(before_today(datetime(2030, 1, 6, 23, 0, tzinfo=timezone(timedelta(hours=8))), self.NOW))

    def test_now_defaults_to_the_current_time(self):
        self.assertTrue(before_today(datetime.utcnow() - timedelta(days=2)))
        self.assertFalse(before_today(datetime.utcnow() + timedelta(days=2)))
