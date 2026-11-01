"""Singapore time (SGT, UTC+8), where ConnectSphere's venues are.

The database and the API keep naive UTC. People read times, and venues keep
their opening hours, in Singapore time. Singapore has no daylight saving, so a
fixed offset is exact.
"""

from datetime import datetime, timedelta, timezone

SGT = timezone(timedelta(hours=8), "SGT")


def to_sgt(value: datetime) -> datetime:
    """A stored naive-UTC (or offset-aware) time as Singapore wall-clock time."""
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(SGT).replace(tzinfo=None)
