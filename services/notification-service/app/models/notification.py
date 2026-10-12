from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Notification(Base):
    __tablename__ = "notifications"
    # One notification per recipient per occurrence of a trigger (SPM-93 AC6).
    # Rows written without an occurrence id leave it NULL, which never collides.
    __table_args__ = (UniqueConstraint("occurrence_id", "user_id", name="uq_notification_occurrence_user"),)

    notificationId: Mapped[str] = mapped_column("notification_id", String(64), primary_key=True)
    userId: Mapped[str] = mapped_column("user_id", String(64), index=True)
    eventId: Mapped[str | None] = mapped_column("event_id", String(64), nullable=True)
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, default="")
    isRead: Mapped[bool] = mapped_column("is_read", Boolean, default=False)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow, index=True)
    # SPM-93 AC2: where the notification takes the reader, and the resource it concerns.
    link: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resourceType: Mapped[str | None] = mapped_column("resource_type", String(64), nullable=True)
    resourceId: Mapped[str | None] = mapped_column("resource_id", String(64), nullable=True)
    occurrenceId: Mapped[str | None] = mapped_column("occurrence_id", String(128), nullable=True)
