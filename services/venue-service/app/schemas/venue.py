from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OperatingHours(BaseModel):
    day: str
    opens: str
    closes: str


class Layout(BaseModel):
    # No fixed whitelist here: the customer explicitly said layout names can
    # be "classroom, theatre, boardroom, banquet, exhibition, or another
    # arrangement" and that the team could "suggest your own list" -- so the
    # published list lives as a guided dropdown in the UI (with an "Other"
    # escape hatch), not a hard server-side restriction. A name is still
    # required to be non-empty regardless of which path it came from.
    name: str = Field(min_length=1)
    capacity: int = Field(gt=0)


class VenueOut(BaseModel):
    venueId: str
    code: str
    name: str
    location: str
    address: str
    floor: str
    description: str
    capacity: int
    facilities: list[str]
    accessibility: list[str]
    layouts: list[Layout]
    operatingHours: list[OperatingHours]
    setupMinutes: int
    turnaroundMinutes: int
    emergencyAccess: str = Field(default="", description="SPM-120: exits, assembly point, and emergency vehicle access.")
    restrictions: str = Field(default="", description="SPM-120: known limits, e.g. noise, load, or no open flames.")
    isActive: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "venueId": "v1",
                "code": "MH-A",
                "name": "Marina Hall A",
                "location": "HarbourFront Centre",
                "address": "1 HarbourFront Walk, Singapore 098585",
                "floor": "2",
                "description": "ConnectSphere's largest multipurpose hall.",
                "capacity": 300,
                "facilities": ["Projector", "PA system", "Video-conferencing", "Stage"],
                "accessibility": ["Wheelchair accessible", "Accessible restrooms nearby"],
                "layouts": [
                    {"name": "Theatre", "capacity": 300},
                    {"name": "Classroom", "capacity": 180},
                    {"name": "Banquet", "capacity": 220},
                ],
                "operatingHours": [{"day": "Mon", "opens": "08:00", "closes": "22:00"}],
                "setupMinutes": 30,
                "turnaroundMinutes": 60,
                "emergencyAccess": "Four exits to the waterfront; assembly point at the promenade.",
                "restrictions": "No open flames; amplified sound ends at 22:00.",
                "isActive": True,
            }
        }
    )


def _required_text(value):
    """Name and location have to be real text, not a blank string."""
    if isinstance(value, str):
        value = value.strip()
    if not isinstance(value, str) or not value:
        raise ValueError("cannot be empty")
    return value


def _whole_minutes(value):
    """A setup or turnaround time is a whole number of minutes, zero or greater."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("must be a whole number of minutes")
    if value < 0:
        raise ValueError("must be zero or greater")
    return value


class VenueCreate(BaseModel):
    code: str = ""
    name: str
    location: str
    address: str = ""
    floor: str = ""
    description: str = ""
    facilities: list[str] = []
    accessibility: list[str] = []
    layouts: list[Layout] = []
    operatingHours: list[OperatingHours] = []
    setupMinutes: int
    turnaroundMinutes: int
    emergencyAccess: str = ""
    restrictions: str = ""

    @field_validator("name", "location", mode="before")
    @classmethod
    def text_is_present(cls, value):
        return _required_text(value)

    @field_validator("setupMinutes", "turnaroundMinutes", mode="before")
    @classmethod
    def minutes_are_whole(cls, value):
        return _whole_minutes(value)


class VenueUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    location: str | None = None
    address: str | None = None
    floor: str | None = None
    description: str | None = None
    facilities: list[str] | None = None
    accessibility: list[str] | None = None
    layouts: list[Layout] | None = None
    operatingHours: list[OperatingHours] | None = None
    setupMinutes: int | None = None
    turnaroundMinutes: int | None = None
    emergencyAccess: str | None = None
    restrictions: str | None = None

    @field_validator("emergencyAccess", "restrictions", mode="before")
    @classmethod
    def blank_when_cleared(cls, value):
        return "" if value is None else value

    @field_validator("name", "location", mode="before")
    @classmethod
    def text_is_present(cls, value):
        if value is None:
            raise ValueError("cannot be empty")
        return _required_text(value)

    @field_validator("setupMinutes", "turnaroundMinutes", mode="before")
    @classmethod
    def minutes_are_whole(cls, value):
        if value is None:
            raise ValueError("must be a whole number of minutes")
        return _whole_minutes(value)


class VenueActivityLogOut(BaseModel):
    logId: str
    venueId: str
    action: str
    changedBy: str
    changedByName: str
    changedByRole: str
    changes: dict
    createdAt: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "logId": "log-1",
                "venueId": "v1",
                "action": "updated",
                "changedBy": "u3",
                "changedByName": "Carol Venue",
                "changedByRole": "venue",
                "changes": {
                    "setupMinutes": {"old": 15, "new": 30},
                    "turnaroundMinutes": {"old": 45, "new": 60},
                },
                "createdAt": "2026-09-20T10:00:00",
            }
        }
    )


class VenueBookingCreate(BaseModel):
    venueId: str
    eventId: str
    startsAt: datetime
    endsAt: datetime
    requirementsSnapshot: str = ""
    coordinatorNotes: str = Field(default="", description="The coordinator's own notes for Venue Staff.")
    acknowledgeWarnings: bool = Field(
        default=False,
        description="Must be true to send a request for a venue whose suitability check has warnings.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "venueId": "v1",
                "eventId": "e1",
                "startsAt": "2026-10-06T09:00:00",
                "endsAt": "2026-10-06T17:00:00",
                "requirementsSnapshot": "Theatre layout, wheelchair access, PA system.",
            }
        }
    )


class VenueBookingDecision(BaseModel):
    reason: str | None = Field(default=None, description="Optional note stored on the booking.")

    model_config = ConfigDict(json_schema_extra={"example": {"reason": "Hall A is free that day."}})


class VenueBookingRejection(BaseModel):
    """SPM-10: why the request is turned down (AC2, required), and optionally another venue to try (AC3)."""

    reason: str | None = Field(default=None, max_length=2000, description="Required. Shown to the coordinator.")
    suggestedVenueId: str | None = Field(
        default=None, description="Optional. An active venue other than the one being rejected."
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"reason": "The hall is booked for maintenance that week.", "suggestedVenueId": "v3"}
        }
    )


class HoldRequest(BaseModel):
    """SPM-116 AC1: Venue Staff hold a pending request's venue until this time (UTC)."""

    expiresAt: datetime = Field(
        description="When the hold expires: in the future, and no later than the event's start. UTC."
    )

    model_config = ConfigDict(json_schema_extra={"example": {"expiresAt": "2030-01-04T17:00:00Z"}})


class HoldOut(BaseModel):
    """SPM-116: a tentative hold on a booking request."""

    expiresAt: datetime
    placedBy: str | None
    placedAt: datetime | None
    state: Literal["active", "expired", "released", "approved", "rejected", "withdrawn", "cancelled"] = Field(
        description=(
            "`active` while it reserves the venue; `expired` once its expiry has passed, when it reserves nothing "
            "and is not a confirmed booking; otherwise how it ended."
        )
    )


class BookingReleaseRequest(BaseModel):
    """SPM-114: event cancellation asks venue-service to free every open booking."""

    eventId: str = Field(min_length=1)

    model_config = ConfigDict(json_schema_extra={"example": {"eventId": "e1"}})


class UnavailabilityCreate(BaseModel):
    """SPM-9: Venue Staff record a block. This does not change any event or booking."""

    startsAt: datetime
    endsAt: datetime
    reason: str = Field(min_length=1, max_length=500)
    note: str = Field(default="", max_length=2000)
    acknowledgeConflicts: bool = Field(
        default=False,
        description=(
            "Required when the block overlaps an approved booking or a pending request with an active hold. "
            "Those bookings stay as they are."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "startsAt": "2030-01-07T10:00:00Z",
                "endsAt": "2030-01-07T12:00:00Z",
                "reason": "maintenance",
                "note": "Lift inspection",
                "acknowledgeConflicts": True,
            }
        }
    )


class UnavailabilityUpdate(BaseModel):
    """SPM-9: change the note, the reason, or the period. A changed period that still overlaps must be confirmed again."""

    startsAt: datetime | None = None
    endsAt: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=2000)
    acknowledgeConflicts: bool = False


class UnavailabilityOut(BaseModel):
    unavailabilityId: str
    venueId: str
    startsAt: datetime
    endsAt: datetime
    reason: str
    note: str = ""
    createdBy: str
    createdAt: datetime


class ReplacementRequest(BaseModel):
    """SPM-115: request another venue for an approved booking affected by a block.

    The booking's time and the event's details are taken from what is already stored.
    """

    venueId: str = Field(min_length=1)
    coordinatorNotes: str = ""
    acknowledgeWarnings: bool = False

    model_config = ConfigDict(json_schema_extra={"example": {"venueId": "v3"}})


class VenueArrangementOut(BaseModel):
    eventId: str
    complete: bool = Field(
        description="True only when the event has requested venues and every one of them is approved."
    )


class BookingRecheck(BaseModel):
    """SPM-86 AC04: try the event's new date and time against this booking. Nothing is saved."""

    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None


class BookingRecheckOut(BaseModel):
    """The booking stays where it is. `conflict` is true when the new occupied window is not free
    or the venue no longer suits the event."""

    bookingId: str
    movedSilently: bool = False
    status: str
    conflict: bool
    verdict: str
    reasons: list[str] = []
    startsAt: datetime
    endsAt: datetime


class BookingReverificationRequest(BaseModel):
    """SPM-71 AC4: event-service asks for an event's confirmed bookings to be re-verified."""

    eventId: str = Field(min_length=1)
    reason: str = Field(default="", description="What changed on the event.")

    model_config = ConfigDict(
        json_schema_extra={"example": {"eventId": "e1", "reason": "Expected attendance: 120 -> 200"}}
    )


class BookingReschedulePreview(BaseModel):
    """SPM-87 AC2: try an event's new date and time against each of its bookings. Nothing is saved."""

    eventId: str = Field(min_length=1)
    startsAt: datetime
    endsAt: datetime


class BookingReschedule(BookingReschedulePreview):
    """SPM-87: move an event's bookings to its new date and time."""

    reason: str = Field(default="", description="Why the event moved, kept on each booking's note.")
    carry: bool = Field(
        default=True,
        description="Carry each approved booking that is free and suitable at the new time across (AC3). False "
        "releases every approved booking so the coordinator can search again.",
    )


class RescheduledBookingOut(BaseModel):
    """One of the event's bookings judged at the new time (SPM-87 AC2), and on apply what happened to it."""

    bookingId: str
    venueId: str
    venueName: str
    status: str = Field(description="The booking's status: `pending` or `approved` before, as it is after on apply.")
    free: bool = Field(description="No confirmed booking, active hold, or unavailability overlaps the new occupied window.")
    suitable: bool = Field(description="The venue passes every other suitability point at the new time.")
    verdict: Literal["suitable", "suitable with warnings", "not suitable"]
    reasons: list[str] = Field(default=[], description="Failures first, then warnings.")
    outcome: Literal["carried", "released", "moved"] | None = Field(
        default=None,
        description="Apply only. `carried`: an approved booking moved to the new time and flagged for Venue Staff "
        "to re-confirm. `released`: an approved booking cancelled because it is not free or suitable (or not "
        "carried), freeing the old time. `moved`: a pending request now asks for the new time.",
    )
    startsAt: datetime
    endsAt: datetime


class VenueBookingOut(BaseModel):
    bookingId: str
    venueId: str
    eventId: str
    requestedBy: str
    status: str = Field(
        description="`pending`, `approved`, `rejected`, `withdrawn`, or `cancelled`."
    )
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime = Field(
        description="Start of the occupied window: the event start minus the venue's current setup time (SPM-112)."
    )
    teardownEndsAt: datetime = Field(
        description="End of the occupied window: the event end plus the venue's current turnaround time (SPM-112)."
    )
    requirementsSnapshot: str
    decisionReason: str | None
    reviewedBy: str | None
    reviewedByName: str | None = Field(
        default=None, description="SPM-8 AC5 and SPM-10 AC6: the name of whoever approved or rejected it."
    )
    suggestedVenueId: str | None = Field(default=None, description="SPM-10 AC3: the venue suggested on rejection.")
    suggestedVenueName: str | None = Field(default=None, description="SPM-10 AC3: that venue's name.")
    reviewedAt: datetime | None
    createdAt: datetime
    eventSnapshot: dict | None = Field(
        default=None, description="The event's facts when the request was sent: name, client, times, needs."
    )
    coordinatorNotes: str = ""
    warnings: list[str] = Field(default=[], description="Suitability warnings the coordinator acknowledged.")
    venueName: str | None = None
    needsReverification: bool = Field(
        default=False, description="A significant event change may have invalidated this booking (SPM-71)."
    )
    reverificationNote: str | None = Field(default=None, description="What changed on the event.")
    hold: HoldOut | None = Field(default=None, description="SPM-116: the tentative hold, if Venue Staff placed one.")
    affectedByUnavailability: bool = Field(
        default=False,
        description="True when this approved booking's occupied window overlaps a venue unavailability block.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "bookingId": "bk-1",
                "venueId": "v1",
                "eventId": "e1",
                "requestedBy": "u2",
                "status": "pending",
                "startsAt": "2026-10-06T09:00:00",
                "endsAt": "2026-10-06T17:00:00",
                "setupStartsAt": "2026-10-06T08:00:00",
                "teardownEndsAt": "2026-10-06T18:00:00",
                "requirementsSnapshot": "Theatre layout, wheelchair access, PA system.",
                "decisionReason": None,
                "reviewedBy": None,
                "reviewedAt": None,
                "createdAt": "2026-09-20T10:00:00",
            }
        }
    )


class SuitabilityRequest(BaseModel):
    """SPM-62. Every field besides the two ids is optional: anything left out
    is taken from the event record, so a caller only sends what differs."""

    eventId: str
    venueId: str
    expectedAttendance: int | None = Field(default=None, ge=0, description="Defaults to the event's expected attendance.")
    layout: str | None = Field(default=None, description="Required layout. Defaults to the event's layout preference.")
    requiredFacilities: list[str] = []
    requiredAccessibility: list[str] = []
    startsAt: datetime | None = Field(default=None, description="Defaults to the event's proposed start.")
    endsAt: datetime | None = Field(default=None, description="Defaults to the event's proposed end.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e1",
                "venueId": "v1",
                "requiredFacilities": ["Stage", "Video-conferencing"],
                "requiredAccessibility": ["Wheelchair accessible"],
            }
        }
    )


class VenueSearchResult(BaseModel):
    """SPM-61: one venue on the shortlist for an event's requirements."""

    venueId: str
    code: str
    name: str
    location: str
    capacity: int
    layout: str | None = Field(default=None, description="The layout searched for, when one was given.")
    layoutCapacity: int = Field(
        description="Capacity in the layout searched for, or the venue's overall capacity when no layout was given."
    )
    headroom: int = Field(description="`layoutCapacity` minus the expected attendance searched for.")
    setupMinutes: int
    turnaroundMinutes: int
    contested: bool = Field(
        description="True when another event's pending request overlaps this period. The venue is still shown."
    )
    verdict: Literal["suitable", "suitable with warnings", "not suitable"] | None = Field(
        default=None,
        description=(
            "SPM-62 AC9: when the search is made for an event (`eventId`), the verdict of the same suitability "
            "check a booking request uses, from the search's filters and, for anything left out, the event's own "
            "requirements. Null for a search without an event."
        ),
    )


class ClashingBooking(BaseModel):
    """SPM-122: one of the two confirmed bookings in a clash, exactly as it stands."""

    bookingId: str
    eventId: str
    eventName: str | None = Field(
        default=None, description="The event's name as sent with the request; null for bookings older than SPM-63."
    )
    status: str
    startsAt: datetime
    endsAt: datetime
    setupStartsAt: datetime = Field(description="Start of the occupied window, from the venue's current setup time.")
    teardownEndsAt: datetime = Field(
        description="End of the occupied window, from the venue's current turnaround time."
    )


class BookingClashOut(BaseModel):
    """SPM-122: two confirmed bookings on one venue whose occupied windows overlap
    once the venue's current setup and turnaround times are applied. Listing a
    clash changes nothing about either booking or its event."""

    venueId: str
    venueName: str
    setupMinutes: int
    turnaroundMinutes: int
    first: ClashingBooking = Field(description="The booking whose occupied window starts first.")
    second: ClashingBooking
    overlapStartsAt: datetime = Field(description="When the two occupied windows start to overlap (UTC).")
    overlapEndsAt: datetime = Field(description="When they stop overlapping (UTC).")


class CalendarEntryOut(BaseModel):
    """SPM-108: one entry on a venue's calendar."""

    kind: Literal["confirmed", "pending", "hold", "expired-hold", "unavailable"] = Field(
        description=(
            "`confirmed` an approved booking; `pending` a request with no active or expired hold; `hold` a "
            "request on an active tentative hold; `expired-hold` a still-pending request whose hold has lapsed; "
            "`unavailable` an unavailability period."
        )
    )
    id: str = Field(description="The booking id, or the unavailability id for `unavailable`.")
    startsAt: datetime = Field(
        description="A booking's occupied window starts at its setup (SPM-112); a block starts when it starts."
    )
    endsAt: datetime = Field(description="A booking's occupied window ends after its turnaround; a block's end.")
    eventId: str | None = None
    eventName: str | None = Field(default=None, description="From the request, else event-service, else the event id.")
    clientOrganisation: str | None = None
    eventStartsAt: datetime | None = Field(default=None, description="The event's advertised start.")
    eventEndsAt: datetime | None = Field(default=None, description="The event's advertised end.")
    booking: VenueBookingOut | None = None
    unavailability: UnavailabilityOut | None = None


class VenueCalendarOut(BaseModel):
    """SPM-108: what holds a venue in a period, with its opening hours (Singapore time)."""

    venueId: str
    venueName: str
    operatingHours: list[OperatingHours]
    setupMinutes: int
    turnaroundMinutes: int
    entries: list[CalendarEntryOut] = Field(description="Earliest first. Empty when nothing holds the venue.")


class SuitabilityReason(BaseModel):
    severity: Literal["failure", "warning"]
    check: str = Field(description="Which rule produced this point, e.g. `capacity` or `clash`.")
    message: str


class SuitabilityOut(BaseModel):
    eventId: str
    venueId: str
    verdict: Literal["suitable", "suitable with warnings", "not suitable"]
    reasons: list[SuitabilityReason] = Field(description="Failures first, then warnings. Empty when suitable.")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "eventId": "e4",
                "venueId": "v4",
                "verdict": "suitable with warnings",
                "reasons": [
                    {
                        "severity": "warning",
                        "check": "capacity",
                        "message": "Expected attendance of 19 is above 90% of what this venue can hold "
                        "in the Boardroom layout (20 people), so it will be a tight fit.",
                    }
                ],
            }
        }
    )


class EventFacts(BaseModel):
    """The parts of event-service's event record that venue-service uses:
    the suitability rule (SPM-62) and booking requests (SPM-63)."""

    expectedAttendance: int = 0
    layoutPreference: str | None = None
    proposedStartAt: datetime | None = None
    proposedEndAt: datetime | None = None
    eventName: str = ""
    status: str = ""
    coordinatorId: str | None = None
    organisationId: str | None = None
    organisationName: str | None = None
    accessibilityNeeds: str = ""
    venueRequirements: str = ""
