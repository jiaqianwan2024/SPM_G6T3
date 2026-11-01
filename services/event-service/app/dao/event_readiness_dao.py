from datetime import datetime

from app.models.event_readiness import EventReadinessItem
from shared.dao.base import BaseDAO


class EventReadinessDAO(BaseDAO):
    def list_for_event(self, event_id: str) -> list[EventReadinessItem]:
        return (
            self.db.query(EventReadinessItem)
            .filter(EventReadinessItem.eventId == event_id)
            .order_by(EventReadinessItem.assignedAt, EventReadinessItem.itemId)
            .all()
        )

    def list_due_between(self, start: datetime, end: datetime) -> list[EventReadinessItem]:
        """Line items whose due date falls in [start, end], soonest first (SPM-5 AC8)."""
        return (
            self.db.query(EventReadinessItem)
            .filter(EventReadinessItem.dueAt.isnot(None), EventReadinessItem.dueAt >= start, EventReadinessItem.dueAt <= end)
            .order_by(EventReadinessItem.dueAt, EventReadinessItem.itemId)
            .all()
        )

    def get(self, item_id: str) -> EventReadinessItem | None:
        return self.db.query(EventReadinessItem).filter(EventReadinessItem.itemId == item_id).one_or_none()
