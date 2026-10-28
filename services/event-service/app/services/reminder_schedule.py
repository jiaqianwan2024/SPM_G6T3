"""SPM-95: run the approaching-event reminder check by itself, once at startup and then at
00:00 Singapore time every day for as long as the service stays up.

A repeat run is safe: a reminder is raised once per event per start date, so only
what is new gets sent. If the service is down at midnight, the check runs again when it
next starts.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.sgt import to_sgt
from app.db import session as db_session
from app.services.reminders import EventReminders

logger = logging.getLogger("event.reminders")


def seconds_until_midnight_sgt(now_utc: datetime) -> float:
    """Seconds from now until the next 00:00 Singapore time. A moment exactly at midnight waits a full day."""
    local = to_sgt(now_utc)
    midnight = datetime.combine(local.date() + timedelta(days=1), datetime.min.time())
    return (midnight - local).total_seconds()


def run_reminders_once() -> None:
    """One check. Any failure is logged, so one bad run never stops the daily schedule."""
    db = db_session.SessionLocal()
    try:
        result = EventReminders(db).run()
        logger.info("reminder check: %d checked, %d reminded", result.checked, len(result.reminded))
    except Exception:
        logger.exception("reminder check failed")
    finally:
        db.close()


async def run_daily(run=run_reminders_once, now=datetime.utcnow, sleep=asyncio.sleep) -> None:
    await asyncio.to_thread(run)
    while True:
        await sleep(seconds_until_midnight_sgt(now()))
        await asyncio.to_thread(run)


def daily_reminders_lifespan(original):
    """Wraps the app's lifespan so the daily check starts with the service and stops with it."""

    @asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(run_daily()) if settings.event_reminder_schedule_enabled else None
        try:
            async with original(app):
                yield
        finally:
            if task is not None:
                task.cancel()

    return lifespan
