from fastapi import APIRouter, Depends, Header

from app.core.config import settings
from app.routers.equipment import get_equipment_service
from app.services.equipment_service import EquipmentService
from shared.auth.service_key import SERVICE_KEY_HEADER, require_service_key
from shared.openapi import error_responses

# Not behind a user token: callers are other services and scheduled jobs, which
# prove themselves with the service key (SPM-95).
router = APIRouter(
    prefix="/internal/equipment",
    tags=["internal"],
    responses=error_responses(403),
)


@router.get(
    "/events/{event_id}/arrangements",
    summary="An event's equipment requests and reservations",
    description="Service key only. Everything the readiness view reads to judge an event's equipment, for a job "
    "with no user token.",
)
def event_arrangements(
    event_id: str,
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    service: EquipmentService = Depends(get_equipment_service),
):
    require_service_key(x_service_key, settings.internal_service_key)
    return {
        "requests": [row.model_dump(mode="json") for row in service.list_requests() if row.eventId == event_id],
        "reservations": [row.model_dump(mode="json") for row in service.list_event_reservations(event_id)],
    }
