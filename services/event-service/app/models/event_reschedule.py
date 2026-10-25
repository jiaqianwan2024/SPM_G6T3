from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EventReschedule(Base):
    """SPM-87 AC9: one row per reschedule, with the old and new period, the
    reason, who moved the event, and when."""

    __tablename__ = "event_reschedules"

    rescheduleId: Mapped[str] = mapped_column("reschedule_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"))
    oldStartAt: Mapped[datetime | None] = mapped_column("old_start_at", DateTime, nullable=True)
    oldEndAt: Mapped[datetime | None] = mapped_column("old_end_at", DateTime, nullable=True)
    newStartAt: Mapped[datetime] = mapped_column("new_start_at", DateTime)
    newEndAt: Mapped[datetime] = mapped_column("new_end_at", DateTime)
    reason: Mapped[str] = mapped_column(Text)
    rescheduledBy: Mapped[str] = mapped_column("rescheduled_by", String(64))
    rescheduledAt: Mapped[datetime] = mapped_column("rescheduled_at", DateTime, default=datetime.utcnow)
