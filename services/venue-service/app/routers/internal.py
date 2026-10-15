from fastapi import APIRouter, Depends, Header, Query

from app.core.config import settings
from app.routers.venue import get_venue_service
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
