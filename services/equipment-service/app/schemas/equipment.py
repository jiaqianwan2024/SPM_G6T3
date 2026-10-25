from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OutOfServiceCounts(BaseModel):
    damaged: int = 0
    maintenance: int = 0
    retired: int = 0


class EquipmentCreate(BaseModel):
    code: str
    name: str
    category: str
    description: str = ""
    totalQuantity: int
    homeLocation: str = ""
    technicalNotes: str = ""
    outOfService: OutOfServiceCounts = Field(default_factory=OutOfServiceCounts)


class EquipmentUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    category: str | None = None
    description: str | None = None
    totalQuantity: int | None = None
    homeLocation: str | None = None
    technicalNotes: str | None = None
    outOfService: OutOfServiceCounts | None = None
    acknowledgeReservationImpact: bool = False


class EquipmentAvailabilityIn(BaseModel):
    equipmentId: str | None = None
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    eventId: str | None = None


class EquipmentAvailabilityOut(BaseModel):
    equipmentId: str
    availableQuantity: int
    serviceableQuantity: int
    reservedQuantity: int


class EquipmentActivityLogOut(BaseModel):
    logId: str
    equipmentId: str
    action: str
    changedBy: str
    changedByName: str
    changedByRole: str
    changes: dict
    createdAt: datetime


class ReservationRelease(BaseModel):
    reason: str = ""


class ReservationReschedulePreview(BaseModel):
    """SPM-87 AC2: try an event's new date and time against its held reservations. Nothing is saved."""

    eventId: str = Field(min_length=1)
    startsAt: datetime
    endsAt: datetime


class ReservationReschedule(ReservationReschedulePreview):
    """SPM-87 AC6: move an event's reservations to its new date and time."""

    reason: str = Field(default="", description="Why the event moved, kept on any flagged reservation.")


class RescheduledReservationOut(BaseModel):
    """One held reservation judged at the new time, and on apply what happened to it."""

    reservationId: str
    equipmentId: str
    equipmentName: str
    quantity: int
    availableQuantity: int = Field(
        description="Units of this equipment free at the new time for this reservation, after other events' "
        "reservations and this event's earlier reservations of the same equipment."
    )
    canMeet: bool
    shortfall: int = 0
    outcome: Literal["moved", "flagged"] | None = Field(
        default=None,
        description="Apply only. `moved`: held at the new time. `flagged`: moved too, but the quantity cannot be "
        "met then, so it is flagged for technical support (AC6); nothing is dropped.",
    )
    needsReverification: bool = False
    startsAt: datetime
    endsAt: datetime


class ReservationReverificationRequest(BaseModel):
    """SPM-71 AC4: event-service asks for an event's held reservations to be re-verified."""

    eventId: str = Field(min_length=1)
    reason: str = Field(default="", description="What changed on the event.")


class EquipmentQuantityReserve(BaseModel):
    eventId: str
    equipmentId: str
    quantity: int
    startsAt: datetime
    endsAt: datetime


class EquipmentOut(BaseModel):
    equipmentId: str
    code: str = ""
    name: str
    category: str
    description: str = ""
    status: str = Field(description="Derived from unit rows: `available`, `maintenance`, or `damaged`.")
    notes: str
    totalQuantity: int = 0
    homeLocation: str = ""
    technicalNotes: str = ""
    outOfService: OutOfServiceCounts = Field(default_factory=OutOfServiceCounts)
    serviceableQuantity: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "equipmentId": "eq1",
                "code": "eq1",
                "name": "Projector PX-200",
                "category": "display",
                "description": "Includes HDMI + VGA adapters",
                "status": "available",
                "notes": "Includes HDMI + VGA adapters",
                "totalQuantity": 4,
                "homeLocation": "Marina Hall store",
                "technicalNotes": "Keep a spare lamp in the same store.",
                "outOfService": {"damaged": 0, "maintenance": 0, "retired": 0},
                "serviceableQuantity": 4,
            }
        }
    )


class EquipmentRequestCreate(BaseModel):
    eventId: str
    equipmentId: str
    quantity: int = 1
    technicalRequirements: str = ""
    startsAt: datetime
    endsAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "equipmentId": "eq1",
                "quantity": 1,
                "technicalRequirements": "HDMI to the lectern.",
                "startsAt": "2026-10-06T08:00:00",
                "endsAt": "2026-10-06T18:00:00",
            }
        }
    )


class EquipmentRequestUnavailable(BaseModel):
    reason: str = Field(min_length=1)
    note: str = ""
    alternativeEquipmentId: str | None = None


class EquipmentPartialFulfillment(BaseModel):
    reservedQuantity: int = Field(ge=0)
    reason: str = ""


class EquipmentReservationAdjust(BaseModel):
    quantity: int = Field(ge=0)


class EquipmentRequestStatusPatch(BaseModel):
    status: str | None = None
    quantity: int | None = Field(default=None, ge=1)
    resubmit: bool = False


class EquipmentRequestRefine(BaseModel):
    quantity: int | None = Field(default=None, ge=1)
    technicalRequirements: str | None = None


class EquipmentRequestReview(BaseModel):
    approve: bool
    reviewNote: str = ""

    model_config = ConfigDict(
        json_schema_extra={"example": {"approve": True, "reviewNote": "Stock is free that day."}}
    )


class EquipmentRequestOut(BaseModel):
    requestId: str
    eventId: str
    equipmentId: str
    quantity: int
    technicalRequirements: str
    requestedBy: str
    status: str = Field(description="`pending`, `approved`, `rejected`, `unavailable`, or `reserved`.")
    startsAt: datetime
    endsAt: datetime
    reviewedBy: str | None
    reviewedAt: datetime | None = None
    reviewNote: str
    decisionReason: str = ""
    reason: str = ""
    alternativeEquipmentId: str | None = None
    suggestedAlternative: str | None = None
    shortfall: int = 0
    reservedQuantity: int = 0
    createdAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "requestId": "req-1",
                "eventId": "e1",
                "equipmentId": "eq1",
                "quantity": 1,
                "technicalRequirements": "HDMI to the lectern.",
                "requestedBy": "u2",
                "status": "pending",
                "startsAt": "2026-10-06T08:00:00",
                "endsAt": "2026-10-06T18:00:00",
                "reviewedBy": None,
                "reviewedAt": None,
                "reviewNote": "",
                "createdAt": "2026-09-20T10:00:00",
            }
        }
    )


class EquipmentReservationOut(BaseModel):
    reservationId: str
    requestId: str
    eventId: str
    equipmentId: str
    quantity: int
    startsAt: datetime
    endsAt: datetime
    status: str
    equipmentName: str | None = None
    needsReverification: bool = Field(
        default=False, description="A significant event change may have invalidated this reservation (SPM-71)."
    )
    reverificationNote: str | None = Field(default=None, description="What changed on the event.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reservationId": "rsv-1",
                "requestId": "req-1",
                "eventId": "e1",
                "equipmentId": "eq1",
                "quantity": 1,
                "startsAt": "2026-10-06T08:00:00",
                "endsAt": "2026-10-06T18:00:00",
                "status": "reserved",
            }
        }
    )


class UpcomingEventOut(BaseModel):
    """SPM-4: one upcoming event that has equipment requirements, as technical support's queue shows it."""

    eventId: str
    eventName: str
    status: str
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    venueName: str = ""
    coordinatorId: str | None = None
    equipmentSummary: str = ""
    equipmentState: str = Field(
        description="`awaiting_review`, `partly_reserved`, `fully_reserved` or `unavailable`."
    )
    needsAttention: bool = False
    needsReverification: bool = False


class EquipmentOutcomeOut(BaseModel):
    reservationId: str = ""
    requestId: str = ""
    eventId: str
    equipmentId: str
    equipmentName: str = ""
    quantity: int = 0
    status: str
    reason: str = ""
    alternativeEquipmentId: str = ""


class EventHoldsRelease(BaseModel):
    eventId: str
    reason: str = "The event was closed"
