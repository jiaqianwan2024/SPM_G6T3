from datetime import datetime

from pydantic import BaseModel, Field


class OutstandingOut(BaseModel):
    category: str
    status: str


class ReminderEventOut(BaseModel):
    eventId: str
    eventName: str
    proposedStartAt: datetime
    coordinatorId: str | None = Field(description="Null when no coordinator is assigned yet.")
    outstanding: list[OutstandingOut]
    sent: list[str] = Field(description="Triggers published for this event.")
    failed: list[str] = Field(description="Triggers notification-service did not accept.")


class ReminderSkippedOut(BaseModel):
    eventId: str
    reason: str


class ReminderRunOut(BaseModel):
    ranAt: datetime
    leadDays: int
    checked: int = Field(description="Events inside the lead time that were looked at.")
    reminded: list[ReminderEventOut]
    skipped: list[ReminderSkippedOut]
