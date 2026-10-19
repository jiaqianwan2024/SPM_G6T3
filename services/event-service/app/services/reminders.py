"""SPM-95: remind staff about approaching events whose arrangements are still outstanding."""

from datetime import datetime, timedelta

from app.core.config import settings
from app.core.sgt import to_sgt
from app.dao.event_dao import EventDAO
from app.models.event import Event
from app.orchestration.clients import arrangement_inputs, publish_notification, users_with_roles
from app.schemas.reminders import OutstandingOut, ReminderEventOut, ReminderRunOut, ReminderSkippedOut
from app.services.audiences import people
from app.services.event_followup import EventFollowUp
from app.services.event_service import COORDINATOR_LEAD, LOCKED_STATUSES
from shared.services.base import BaseService

STAFF_ROLES = ["venue", "techsupport", COORDINATOR_LEAD]


def _describe(pending: list[dict]) -> str:
    """e.g. "Venue (outstanding), Equipment (needs attention)"."""
    return ", ".join(f"{row['category'].capitalize()} ({row['status'].replace('_', ' ')})" for row in pending)


class EventReminders(BaseService):
    def __init__(self, db):
        super().__init__(db)
        self.events = EventDAO(db)
        self.followup = EventFollowUp(db)

    def run(self, now: datetime | None = None) -> ReminderRunOut:
        """Looks at every event starting within the lead time that is not closed, and
        publishes a reminder for each one with something outstanding. Safe to run as
        often as you like: a reminder is one occurrence per event per start date, so a
        repeat run notifies nobody twice."""
        now = now or datetime.utcnow()
        lead = settings.event_reminder_lead_days
        rows = self.events.list_approaching(now, now + timedelta(days=lead), list(LOCKED_STATUSES))
        directory = users_with_roles(STAFF_ROLES) or {}
        reminded, skipped = [], []
        for event in rows:
            inputs = arrangement_inputs(event.eventId)
            if inputs is None:
                skipped.append(ReminderSkippedOut(eventId=event.eventId, reason="Its arrangements could not be read"))
                continue
            pending = self.followup.not_ready(event.eventId, *inputs)
            if pending:
                reminded.append(self._remind(event, pending, directory))
        return ReminderRunOut(ranAt=now, leadDays=lead, checked=len(rows), reminded=reminded, skipped=skipped)

    def _remind(self, event: Event, pending: list[dict], directory: dict[str, dict]) -> ReminderEventOut:
        context = {
            "eventName": event.eventName,
            "eventDate": f"{to_sgt(event.proposedStartAt):%d %b %Y}",
            "outstanding": _describe(pending),
        }
        categories = {row["category"].lower() for row in pending}
        # AC2 and AC7: the assigned coordinator, or the lead when nobody is assigned.
        sends = [("readiness.reminder", "coordinator") if event.coordinatorId else ("readiness.reminder.unassigned", COORDINATOR_LEAD)]
        # AC3: whoever can act on an outstanding venue or equipment line is told directly.
        if "venue" in categories:
            sends.append(("readiness.reminder.venue", "venue"))
        if "equipment" in categories:
            sends.append(("readiness.reminder.equipment", "techsupport"))
        sent, failed = [], []
        for trigger, audience in sends:
            recipients = people(event, [audience], directory)
            if not recipients:
                continue
            occurrence = f"{event.eventId}:{trigger}:{event.proposedStartAt:%Y%m%d}"  # AC5
            ok = publish_notification(
                trigger, event.eventId, occurrence, recipients, context, resource={"type": "event", "id": event.eventId}
            )
            (sent if ok else failed).append(trigger)
        return ReminderEventOut(
            eventId=event.eventId,
            eventName=event.eventName,
            proposedStartAt=event.proposedStartAt,
            coordinatorId=event.coordinatorId,
            outstanding=[OutstandingOut(**row) for row in pending],
            sent=sent,
            failed=failed,
        )
