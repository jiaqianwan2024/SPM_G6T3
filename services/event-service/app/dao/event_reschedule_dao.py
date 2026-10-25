from sqlalchemy.orm import Session

from app.models.event_reschedule import EventReschedule


class EventRescheduleDAO:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: EventReschedule) -> None:
        self.db.add(row)

    def list_by_event(self, event_id: str) -> list[EventReschedule]:
        return (
            self.db.query(EventReschedule)
            .filter(EventReschedule.eventId == event_id)
            .order_by(EventReschedule.rescheduledAt.asc())
            .all()
        )
