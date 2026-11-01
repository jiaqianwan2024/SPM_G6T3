from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query

from app.core.config import settings
from app.routers.venue import get_venue_service
from app.schemas.venue import VenueBookingOut
from app.services.venue_service import VenueService
from shared.auth.service_key import SERVICE_KEY_HEADER, require_service_key
from shared.openapi import error_responses

# Not behind a user token: callers are other services and scheduled jobs, which
# prove themselves with the service key (SPM-95).
router = APIRouter(
    prefix="/internal/venues",
    tags=["internal"],
    responses=error_responses(403),
)


@router.get(
    "/bookings/public-summary",
    summary="Approved venue name and location for an event",
    description="Service key only. The same answer as the signed-in route, for a job with no user token.",
)
def public_booking_summary(
    eventId: str = Query(..., description="Event id."),
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    service: VenueService = Depends(get_venue_service),
):
    require_service_key(x_service_key, settings.internal_service_key)
    return service.public_summary(eventId)


@router.get(
    "/bookings",
    response_model=list[VenueBookingOut],
    summary="An event's venue bookings",
    description="Service key only. Every booking of one event, whatever its status, the same rows as the "
    "signed-in list. Event-service reads them for the safety handoff (SPM-120), which technical support "
    "send without being allowed to read venue bookings themselves.",
)
def event_bookings(
    eventId: str = Query(..., description="Event id."),
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    service: VenueService = Depends(get_venue_service),
):
    require_service_key(x_service_key, settings.internal_service_key)
    return service.list_bookings(None, eventId, None)


@router.get(
    "/bookings/public-summaries",
    summary="Approved venue name and location for several events",
    description="Service key only. The public summary for each comma-separated event id, keyed by event id, "
    "so a list of events (the SPM-4 queue) needs one call rather than one per event.",
)
def public_booking_summaries(
    eventIds: str = Query(..., description="Comma-separated event ids, e.g. `e1,e2`."),
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    service: VenueService = Depends(get_venue_service),
):
    require_service_key(x_service_key, settings.internal_service_key)
    ids = dict.fromkeys(part.strip() for part in eventIds.split(",") if part.strip())
    return {event_id: service.public_summary(event_id) for event_id in ids}


@router.get(
    "/holds/expired",
    summary="Tentative holds that ran out in a period",
    description="Service key only. Every hold whose expiry fell after `since` and at or before `until` and that was "
    "not released first, with its event and venue, so event-service's daily check can tell each coordinator "
    "(SPM-93 AC4, SPM-116 AC5).",
)
def expired_holds(
    since: datetime = Query(..., description="Start of the period, exclusive, UTC."),
    until: datetime = Query(..., description="End of the period, inclusive, UTC."),
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    service: VenueService = Depends(get_venue_service),
):
    require_service_key(x_service_key, settings.internal_service_key)
    return service.expired_holds(since, until)
