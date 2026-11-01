import unittest
from datetime import datetime, timedelta, timezone

from app.core.sgt import to_sgt


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
