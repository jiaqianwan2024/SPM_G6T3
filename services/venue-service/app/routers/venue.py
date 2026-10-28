from datetime import datetime

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.venue_activity_log_dao import VenueActivityLogDAO
from app.dao.venue_booking_dao import VenueBookingDAO
from app.dao.venue_dao import VenueDAO
from app.dao.venue_unavailability_dao import VenueUnavailabilityDAO
from app.db.session import get_db
from app.orchestration.clients import fetch_event_facts, notify_coordinator, notify_venue_staff
from app.schemas.venue import (
    BookingClashOut,
    BookingRecheck,
    BookingRecheckOut,
    BookingReleaseRequest,
    BookingReschedule,
    BookingRestoreRequest,
    ReleasedBookingOut,
    BookingReschedulePreview,
    BookingReverificationRequest,
    RescheduledBookingOut,
    HoldRequest,
    SuitabilityOut,
    SuitabilityRequest,
    VenueActivityLogOut,
    ReplacementRequest,
    UnavailabilityCreate,
    UnavailabilityOut,
    UnavailabilityUpdate,
    VenueBookingCreate,
    VenueBookingDecision,
    VenueBookingRejection,
    VenueArrangementOut,
    VenueBookingOut,
    VenueCalendarOut,
    VenueCreate,
    VenueOut,
    VenueSearchResult,
    VenueUpdate,
)
from app.services.venue_service import VenueService
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/venues",
    tags=["venues"],
    responses=error_responses(401),
)

# SPM-17 AC1/AC5: only these roles can reach the catalogue at all; Event
# Organisers and Attendees are excluded, enforced here rather than only by
# hiding the tab in the frontend.
CATALOGUE_READER_ROLES = {"coordinator", "venue", "techsupport"}
# SPM-62: coordinators check before requesting a venue; Venue Staff can run
# the same check when assessing a request.
SUITABILITY_ROLES = {"coordinator", "venue"}
# SPM-63: coordinators follow their requests; Venue Staff work the pending queue.
BOOKING_READER_ROLES = {"coordinator", "venue"}
# SPM-61: coordinators shortlist venues for their events; Venue Staff can use the
# same search to find an alternative to suggest when they reject a request (SPM-10).
SEARCH_ROLES = {"coordinator", "venue"}
# SPM-108 AC8: every internal role reads any venue's calendar; organisers and attendees are clients.
CALENDAR_READER_ROLES = {"coordinator", "coordinatorlead", "venue", "techsupport", "safety"}


def get_venue_service(db: Session = Depends(get_db)) -> VenueService:
    return VenueService(
        db, VenueDAO(db), VenueActivityLogDAO(db), VenueBookingDAO(db), VenueUnavailabilityDAO(db)
    )


@router.get(
    "",
    response_model=list[VenueOut],
    summary="List venues",
    description=(
        "Venue catalogue for coordinators, venue staff, and technical support. "
        "Retired venues are omitted unless `includeRetired` is true."
    ),
    responses=error_responses(403, 503),
)
def list_venues(
    includeRetired: bool = Query(False, description="Include retired venues in the list."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return service.list_venues(include_retired=includeRetired)


@router.get(
    "/bookings",
    response_model=list[VenueBookingOut],
    summary="List venue booking requests",
    description=(
        "Coordinators and venue staff. Oldest first. `status=pending` is Venue Staff's pending queue; "
        "`eventId` shows an event's venue arrangement."
    ),
    responses=error_responses(403, 503),
)
def list_bookings(
    status: str | None = Query(
        None, description="`pending`, `approved`, `rejected`, `withdrawn`, or `cancelled`."
    ),
    eventId: str | None = Query(None, description="Only this event's requests."),
    venueId: str | None = Query(None, description="Only this venue's requests."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=BOOKING_READER_ROLES)
    return service.list_bookings(status, eventId, venueId)


@router.get(
    "/bookings/arrangement",
    response_model=VenueArrangementOut,
    summary="Whether an event's venue arrangements are complete",
    description=(
        "Complete only when the event has at least one requested venue and every pending or approved "
        "booking is approved. Withdrawn, rejected, and cancelled bookings are not part of the arrangement."
    ),
    responses=error_responses(403, 503),
)
def venue_arrangement(
    eventId: str = Query(..., description="The event whose venue bookings to judge."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=BOOKING_READER_ROLES)
    return VenueArrangementOut(eventId=eventId, complete=service.arrangements_complete(eventId))


@router.get(
    "/bookings/public-summary",
    summary="Approved venue name and location for an event",
    description="Any signed-in user. Does not include the venue catalogue or booking notes.",
)
def public_booking_summary(
    eventId: str = Query(..., description="Event id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url)
    return service.public_summary(eventId)


@router.get(
    "/bookings/clashes",
    response_model=list[BookingClashOut],
    summary="Confirmed bookings that clash once setup and turnaround are included",
    description=(
        "SPM-122. Venue Staff only. Every pair of approved bookings on the same venue whose occupied windows "
        "(event start minus the venue's setup time to event end plus its turnaround time, using the venue's "
        "current times) overlap, with both events and the overlapping times. Windows that only touch are not "
        "listed. Read only: the bookings and their events are left exactly as they are. Pass `venueId` for one "
        "venue."
    ),
    responses=error_responses(403, 404, 503),
)
def booking_clashes(
    venueId: str | None = Query(None, description="Only this venue's clashes, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.booking_clashes(venueId)


@router.get(
    "/bookings/{booking_id}",
    response_model=VenueBookingOut,
    summary="Get a venue booking request",
    description="Coordinators and venue staff. Includes the event facts, notes, and warnings sent with it.",
    responses=error_responses(403, 404, 503),
)
def get_booking(
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=BOOKING_READER_ROLES)
    return service.get_booking(booking_id)


@router.get(
    "/search",
    response_model=list[VenueSearchResult],
    summary="Search venues against an event's requirements",
    description=(
        "SPM-61. Active venues that fit every filter, ordered by name. With `startsAt` and `endsAt` (UTC), "
        "a venue is left out when the period falls outside its opening hours, or when a confirmed booking or "
        "an unavailability period overlaps the period widened by the venue's setup and turnaround time; "
        "another event's pending request only marks it `contested`. Pass `eventId` to ignore that event's own "
        "requests and to give each venue the `verdict` of the SPM-62 suitability check for that event (SPM-62 "
        "AC9); anything left out of the search comes from the event. `facility` and `accessibility` can be "
        "repeated. Coordinators and venue staff."
    ),
    responses=error_responses(403, 404, 422, 503),
)
def search_venues(
    startsAt: datetime | None = Query(None, description="Start of the period, e.g. `2027-03-03T10:00:00Z`."),
    endsAt: datetime | None = Query(None, description="End of the period. Required when `startsAt` is given."),
    minCapacity: int | None = Query(
        None, ge=0, description="Expected attendance; capacity in the layout must reach it. None means no minimum."
    ),
    location: str | None = Query(None, description="Part of the venue's location, e.g. `HarbourFront`."),
    layout: str | None = Query(None, description="Required layout, e.g. `Theatre`."),
    facility: list[str] = Query(default=[], description="A required facility. Repeat for more than one."),
    accessibility: list[str] = Query(default=[], description="A required accessibility feature. Repeat for more."),
    eventId: str | None = Query(None, description="The event searching, so its own requests are not counted."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=SEARCH_ROLES)
    return service.search_venues(
        starts_at=startsAt,
        ends_at=endsAt,
        min_capacity=minCapacity,
        location=location,
        layout=layout,
        facilities=facility,
        accessibility=accessibility,
        exclude_event_id=eventId,
        event=fetch_event_facts(eventId, authorization) if eventId else None,
    )


@router.get(
    "/{venue_id}",
    response_model=VenueOut,
    summary="Get venue",
    description="Single venue, including retired ones. Coordinators, venue staff, and technical support only.",
    responses=error_responses(403, 404, 503),
)
def get_venue(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return service.get_venue(venue_id)


@router.post(
    "",
    response_model=VenueOut,
    status_code=201,
    summary="Create venue",
    description="Venue staff only. Capacity is derived from the highest layout capacity.",
    responses=error_responses(403, 503),
)
def create_venue(
    body: VenueCreate,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.create_venue(body, caller)


@router.patch(
    "/{venue_id}",
    response_model=VenueOut,
    summary="Update venue",
    description="Venue staff only. Partial update; omitted fields are left unchanged.",
    responses=error_responses(403, 404, 503),
)
def update_venue(
    body: VenueUpdate,
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.update_venue(venue_id, body, caller)


@router.post(
    "/{venue_id}/retire",
    response_model=VenueOut,
    summary="Retire venue",
    description=(
        "Venue staff only. Soft-deletes the venue (`isActive=false`). "
        "Fails with 409 if there are confirmed upcoming bookings unless `confirm` is true."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def retire_venue(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    confirm: bool = Query(
        False, description="Required if confirmed upcoming bookings would be affected."
    ),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.retire_venue(venue_id, caller, confirm)


@router.post(
    "/{venue_id}/unavailability",
    response_model=UnavailabilityOut,
    status_code=201,
    summary="Record a venue unavailability block",
    description=(
        "Venue Staff only. Saves the block and does not change the event or its bookings. "
        "An approved booking, or a pending request with an active hold, whose occupied window overlaps "
        "the block must be confirmed with `acknowledgeConflicts`. The assigned coordinator is then notified. "
        "A pending request with no hold does not need confirmation."
    ),
    responses=error_responses(403, 404, 409, 422, 503),
)
def record_unavailability(
    body: UnavailabilityCreate,
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    saved = service.record_unavailability(venue_id, body, caller)
    _notify_alternative_arrangements(service, venue_id, saved.startsAt, saved.endsAt, saved.reason, authorization)
    return saved


@router.get(
    "/{venue_id}/unavailability",
    response_model=list[UnavailabilityOut],
    summary="List a venue's unavailability blocks",
    description="Coordinators, venue staff, and technical support. Active blocks only; a cancelled block is removed.",
    responses=error_responses(403, 404, 503),
)
def list_unavailability(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return service.list_unavailability(venue_id)


@router.get(
    "/{venue_id}/calendar",
    response_model=VenueCalendarOut,
    summary="A venue's calendar",
    description=(
        "SPM-108. Coordinators, the Coordinator Lead, Venue Staff, Technical Support and Safety Officers. "
        "Every confirmed booking, pending request, active or expired tentative hold, and unavailability "
        "period whose window overlaps the range, earliest first. A booking's window is its occupied window, "
        "setup and turnaround included; `eventStartsAt` / `eventEndsAt` are the advertised times. Opening "
        "hours are Singapore time. Leave out `from` and `to` for everything. An empty range returns no entries."
    ),
    responses=error_responses(403, 404, 503),
)
def venue_calendar(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    starts_at: datetime | None = Query(None, alias="from", description="Range start (UTC unless an offset is given)."),
    ends_at: datetime | None = Query(None, alias="to", description="Range end; must be after `from`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CALENDAR_READER_ROLES)
    return service.calendar(venue_id, starts_at, ends_at, authorization)


@router.patch(
    "/{venue_id}/unavailability/{unavailability_id}",
    response_model=UnavailabilityOut,
    summary="Change a venue unavailability block",
    description=(
        "Venue Staff only. The note, the reason, and the period can change. A changed period that overlaps "
        "an approved booking or an active hold must be confirmed again with `acknowledgeConflicts`. "
        "Bookings and events are left as they are."
    ),
    responses=error_responses(403, 404, 409, 422, 503),
)
def update_unavailability(
    body: UnavailabilityUpdate,
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    unavailability_id: str = Path(..., description="Unavailability block id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    saved = service.update_unavailability(venue_id, unavailability_id, body, caller)
    if body.startsAt is not None or body.endsAt is not None:
        _notify_alternative_arrangements(service, venue_id, saved.startsAt, saved.endsAt, saved.reason, authorization)
    return saved


@router.delete(
    "/{venue_id}/unavailability/{unavailability_id}",
    status_code=204,
    summary="Cancel a venue unavailability block",
    description="Venue Staff only. Removes the block, so that time can be searched and approved again.",
    responses=error_responses(403, 404, 503),
)
def cancel_unavailability(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    unavailability_id: str = Path(..., description="Unavailability block id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    service.cancel_unavailability(venue_id, unavailability_id, caller)


def _notify_alternative_arrangements(service, venue_id, starts_at, ends_at, reason, authorization) -> None:
    """Tell each affected event's coordinator, in the app, that they need another arrangement.

    Best effort: the block is already saved. An event with no coordinator is skipped. A failure to
    reach event-service or notification-service does not undo the block.
    """
    for alert in service.unavailability_alerts(venue_id, starts_at, ends_at):
        event_id = alert["eventId"]
        try:
            event = fetch_event_facts(event_id, authorization)
        except Exception:
            continue
        if not event.coordinatorId:
            continue
        name = event.eventName or alert["eventName"] or event_id
        notify_coordinator(
            event.coordinatorId,
            event_id,
            "Venue unavailable",
            (
                f"{alert['venueName']} ({venue_id}) is unavailable ({reason}). "
                f"Alternative arrangements are required for {name}."
            ),
            authorization or "",
            "venue.unavailability",
        )


@router.get(
    "/{venue_id}/activity-log",
    response_model=list[VenueActivityLogOut],
    summary="Venue activity log",
    description="Create, update, and retire history for a venue. Coordinators, venue staff, and technical support only.",
    responses=error_responses(403, 404, 503),
)
def get_venue_activity_log(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return service.get_activity_log(venue_id)


@router.post(
    "/suitability",
    response_model=SuitabilityOut,
    summary="Check whether a venue suits an event",
    description=(
        "Coordinators and venue staff. Returns `suitable`, `suitable with warnings`, or `not suitable`, "
        "with a reason for every failure or warning. Anything not sent is taken from the event record. "
        "Times are sent in UTC; opening hours, and the times in each reason, are Singapore time (SGT)."
    ),
    responses=error_responses(403, 404, 503),
)
def check_suitability(
    body: SuitabilityRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=SUITABILITY_ROLES)
    event = fetch_event_facts(body.eventId, authorization)
    return service.check_suitability(body, event)


@router.post(
    "/bookings",
    response_model=VenueBookingOut,
    status_code=201,
    summary="Request a venue booking",
    description=(
        "Only the event's assigned coordinator, for an event approved for planning. Refused with 409 when the "
        "venue fails the suitability check, when warnings are not acknowledged (`acknowledgeWarnings`), or when "
        "this event already has a pending or approved booking for the same venue. Other venues can be "
        "requested at the same time. Each venue is checked on its own. Venue Staff are notified."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def create_booking(
    body: VenueBookingCreate,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    event = fetch_event_facts(body.eventId, authorization)
    booking = service.request_booking(body, caller, event)
    notify_venue_staff(*service.venue_staff_notice(booking, "requested"), authorization)
    return booking


@router.post(
    "/bookings/reverification",
    response_model=list[VenueBookingOut],
    summary="Mark an event's confirmed bookings for re-verification",
    description="Coordinators and safety officers (SPM-71 AC4, SPM-120). Called by event-service when a "
    "significant event change is saved, or when a safety officer asks for the venue to be reviewed again. "
    "Each `approved` booking for the event gets `needsReverification` and the reason; its status is "
    "unchanged, so the venue stays held. Returns the bookings marked.",
    responses=error_responses(403, 503),
)
def flag_bookings_for_reverification(
    body: BookingReverificationRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator", "safety"})
    return service.flag_for_reverification(body.eventId, body.reason, authorization)


@router.post(
    "/bookings/release",
    response_model=list[ReleasedBookingOut],
    summary="Release every open venue booking for an event",
    description=(
        "The event's assigned coordinator, or an organiser from the event's own client organisation. For event "
        "cancellation: every pending request and approved booking for the event becomes `cancelled`. Rejected, "
        "withdrawn, and already cancelled rows stay as they are."
    ),
    responses=error_responses(403, 404, 503),
)
def release_event_bookings(
    body: BookingReleaseRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"organiser", "coordinator"})
    service.check_release_allowed(caller, fetch_event_facts(body.eventId, authorization))
    return service.release_event_bookings(body.eventId)


@router.post(
    "/bookings/restore",
    response_model=list[VenueBookingOut],
    summary="Undo a cancellation's venue release",
    description=(
        "SPM-88 AC9. The same people as the release. Event-service calls it when a cancellation fails after its "
        "venue release, so the event and its bookings never disagree. Each named booking of the event that is "
        "still `cancelled` gets back the status it had, and any tentative hold the release ended. 409 when a "
        "booking's venue was approved for someone else in the meantime."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def restore_event_bookings(
    body: BookingRestoreRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"organiser", "coordinator"})
    service.check_release_allowed(caller, fetch_event_facts(body.eventId, authorization))
    return service.restore_event_bookings(body.eventId, body.bookings)


@router.post(
    "/bookings/reschedule/preview",
    response_model=list[RescheduledBookingOut],
    summary="Check an event's bookings at a new date and time",
    description="SPM-87 AC2. The event's assigned coordinator only. Each pending request and approved booking is "
    "judged at the new occupied window with the same suitability check as a new request, the event's own bookings "
    "left out: `free` when nothing else holds the venue then, `suitable` when it passes every other point. "
    "Nothing is moved.",
    responses=error_responses(403, 404, 422, 503),
)
def preview_reschedule(
    body: BookingReschedulePreview,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.preview_reschedule(body, caller, fetch_event_facts(body.eventId, authorization))


@router.post(
    "/bookings/reschedule",
    response_model=list[RescheduledBookingOut],
    summary="Move an event's bookings to its new date and time",
    description="SPM-87. The event's assigned coordinator only; event-service calls it when a reschedule is "
    "applied. An approved booking that is free and suitable at the new time is carried across and flagged for "
    "Venue Staff to re-confirm, and they are notified. Any other approved booking, or every one when `carry` is "
    "false, is released. A pending request takes the new time. The old times are freed only here. 409 when "
    "another event took a venue at the new time meanwhile; nothing is moved then.",
    responses=error_responses(403, 404, 409, 422, 503),
)
def reschedule_bookings(
    body: BookingReschedule,
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.reschedule_bookings(body, caller, fetch_event_facts(body.eventId, authorization), authorization)


@router.post(
    "/bookings/{booking_id}/withdraw",
    response_model=VenueBookingOut,
    summary="Withdraw a venue booking request",
    description="The event's assigned coordinator (SPM-46), while it is still pending. Venue Staff are notified.",
    responses=error_responses(403, 404, 409, 503),
)
def withdraw_booking(
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    event = fetch_event_facts(service.get_booking(booking_id).eventId, authorization)
    booking = service.withdraw_booking(booking_id, caller, event.coordinatorId)
    notify_venue_staff(*service.venue_staff_notice(booking, "withdrawn"), authorization)
    return booking


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=VenueBookingOut,
    summary="Cancel one approved venue booking",
    description=(
        "The event's assigned coordinator, or Venue Staff. Only an `approved` booking can be cancelled. "
        "The event's other bookings stay. Venue Staff are notified."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def cancel_booking(
    booking_id: str = Path(..., description="Booking id of an approved booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator", "venue"})
    event = fetch_event_facts(service.get_booking(booking_id).eventId, authorization)
    booking = service.cancel_booking(booking_id, caller, event.coordinatorId)
    # SPM-93 AC5: whoever cancelled is not told about their own action.
    notify_venue_staff(*service.venue_staff_notice(booking, "cancelled"), authorization, skip_user_id=caller["userId"])
    return booking


@router.post(
    "/bookings/{booking_id}/replacement",
    response_model=VenueBookingOut,
    status_code=201,
    summary="Request a replacement venue",
    description=(
        "The event's assigned coordinator, for an approved booking affected by an unavailability block. "
        "The new venue is checked on its own for suitability, availability, and conflicts, using the "
        "booking's existing time and the event's current details. The event is not changed. "
        "When the request is accepted, the original booking is cancelled and stays readable. "
        "The event's other bookings stay. Venue Staff are notified."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def request_replacement(
    body: ReplacementRequest,
    booking_id: str = Path(..., description="Approved booking affected by an unavailability block."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    original = service.get_booking(booking_id)
    event = fetch_event_facts(original.eventId, authorization)
    created = service.request_replacement(booking_id, body, caller, event)
    notify_venue_staff(*service.venue_staff_notice(created, "requested"), authorization)
    notify_venue_staff(*service.venue_staff_notice(service.get_booking(booking_id), "cancelled"), authorization)
    return created


@router.post(
    "/bookings/{booking_id}/hold",
    response_model=VenueBookingOut,
    summary="Place a tentative hold on a pending booking request",
    description=(
        "SPM-116. Venue staff only. Reserves the venue for the request's occupied window until `expiresAt`, "
        "which must be in the future and no later than the event's start. Refused (409) when the request is not "
        "pending, already has an active hold, or the venue is already taken for that window. The event's "
        "assigned coordinator is told in the app until when the venue is held. An expired hold reserves nothing."
    ),
    responses=error_responses(403, 404, 409, 422, 503),
)
def place_hold(
    body: HoldRequest,
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    event = fetch_event_facts(service.get_booking(booking_id).eventId, authorization)
    booking = service.place_hold(booking_id, body.expiresAt, caller)
    if event.coordinatorId:
        notify_coordinator(
            event.coordinatorId, booking.eventId, *service.hold_notice(booking, event), authorization
        )
    return booking


@router.post(
    "/bookings/{booking_id}/hold/release",
    response_model=VenueBookingOut,
    summary="Release a tentative hold before it expires",
    description="SPM-116. Venue staff only. The venue is free again for that window. 409 when there is no active hold.",
    responses=error_responses(403, 404, 409, 503),
)
def release_hold(
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return service.release_hold(booking_id)


@router.post(
    "/bookings/{booking_id}/recheck",
    response_model=BookingRecheckOut,
    summary="Re-check a booking against a new date and time",
    description="SPM-86 AC04. Reports whether the venue still suits the event and is free for the new "
    "occupied window. The booking is not moved.",
    responses=error_responses(403, 404, 409, 503),
)
def recheck_booking(
    body: BookingRecheck,
    booking_id: str = Path(..., description="Booking id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator", "venue"})
    booking = service.get_booking(booking_id)
    event = fetch_event_facts(booking.eventId, authorization)
    return service.recheck_booking(booking_id, event, body.proposedStartAt, body.proposedEndAt)


@router.post(
    "/bookings/{booking_id}/reconfirm",
    response_model=VenueBookingOut,
    summary="Re-confirm a flagged booking at the event's current details",
    description="SPM-86 AC05 and AC06. Venue staff only. When the venue still suits the event and is free, "
    "the booking takes the event's current start and end and the re-verification flag clears. When it does "
    "not, that booking is released and the coordinator is asked to search again. Other bookings stay.",
    responses=error_responses(403, 404, 409, 503),
)
def reconfirm_booking(
    booking_id: str = Path(..., description="Booking id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    booking = service.get_booking(booking_id)
    event = fetch_event_facts(booking.eventId, authorization)
    return service.reconfirm_booking(booking_id, event, authorization)


@router.post(
    "/bookings/{booking_id}/approve",
    response_model=VenueBookingOut,
    summary="Approve a venue booking",
    description=(
        "SPM-8. Venue staff only. Turns a pending request into a confirmed booking that reserves the venue for "
        "its occupied window (event start minus setup time to event end plus turnaround time), and records who "
        "approved it and when. Refused with 409, leaving the request pending, when the booking is no longer "
        "`pending` or the window overlaps a confirmed booking, an active tentative hold, or an unavailability "
        "period. An expired hold does not block approval. The event's assigned coordinator is told in the app."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def approve_booking(
    body: VenueBookingDecision,
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    booking = service.approve_booking(booking_id, caller["userId"], body.reason, caller.get("userName"))
    _tell_coordinator_of_decision(service, booking, authorization)
    return booking


@router.post(
    "/bookings/{booking_id}/reject",
    response_model=VenueBookingOut,
    summary="Reject a venue booking",
    description=(
        "SPM-10. Venue staff only. A `reason` is required (422 when blank); `suggestedVenueId` optionally "
        "names another active venue (422 when it is unknown, retired, or the same venue). The request becomes "
        "`rejected`, leaves the pending queue, ends any tentative hold so it reserves nothing, and records who "
        "rejected it, why, and when. Fails with 409 if the booking is no longer `pending`, so a rejected request "
        "can no longer be approved or changed. The event's assigned coordinator is told in the app, with the reason and "
        "any suggested venue."
    ),
    responses=error_responses(403, 404, 409, 422, 503),
)
def reject_booking(
    body: VenueBookingRejection,
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    service: VenueService = Depends(get_venue_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    booking = service.reject_booking(
        booking_id, caller["userId"], body.reason, caller.get("userName"), body.suggestedVenueId
    )
    _tell_coordinator_of_decision(service, booking, authorization)
    return booking


def _tell_coordinator_of_decision(service: VenueService, booking: VenueBookingOut, authorization: str | None) -> None:
    """Best effort, after the decision is saved: the event's assigned coordinator is told in the app.
    An unreachable event-service only skips the notice."""
    try:
        event = fetch_event_facts(booking.eventId, authorization)
    except Exception:
        return
    if event.coordinatorId:
        title, body, notice_type = service.decision_notice(booking, event)
        notify_coordinator(event.coordinatorId, booking.eventId, title, body, authorization or "", notice_type)
