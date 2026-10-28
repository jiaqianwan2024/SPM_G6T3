from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.equipment_activity_log_dao import EquipmentActivityLogDAO
from app.dao.equipment_dao import EquipmentDAO
from app.dao.equipment_request_dao import EquipmentRequestDAO
from app.dao.equipment_reservation_dao import EquipmentReservationDAO
from app.dao.equipment_unit_dao import EquipmentUnitDAO
from app.db.session import get_db
from app.schemas.equipment import (
    EquipmentOutcomeOut,
    EquipmentPartialFulfillment,
    EquipmentReservationAdjust,
    EventHoldsRelease,
    ReleasedReservationOut,
    ReservationRestoreRequest,
    EquipmentActivityLogOut,
    EquipmentAvailabilityIn,
    EquipmentCreate,
    EquipmentOut,
    EquipmentQuantityReserve,
    EquipmentRequestCreate,
    EquipmentRequestOut,
    EquipmentRequestRefine,
    EquipmentRequestReview,
    EquipmentRequestStatusPatch,
    EquipmentRequestUnavailable,
    EquipmentReservationOut,
    EquipmentUpdate,
    RescheduledReservationOut,
    ReservationRelease,
    ReservationReschedule,
    ReservationReschedulePreview,
    ReservationReverificationRequest,
    TechDashboardOut,
    UpcomingEventOut,
)
from app.orchestration.clients import check_event_access, fetch_event_coordinator, fetch_upcoming_events, fetch_venue_name
from app.services.equipment_service import EquipmentService, require_assigned_coordinator
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.exceptions.http import forbidden
from shared.openapi import error_responses

router = APIRouter(
    prefix="/equipment",
    tags=["equipment"],
    responses=error_responses(401),
)


def get_equipment_service(db: Session = Depends(get_db)) -> EquipmentService:
    return EquipmentService(
        db,
        EquipmentDAO(db),
        EquipmentUnitDAO(db),
        EquipmentActivityLogDAO(db),
        EquipmentReservationDAO(db),
        EquipmentRequestDAO(db),
    )


@router.get(
    "",
    response_model=list[EquipmentOut],
    summary="List equipment",
    description="Catalogue of equipment types. `status` is derived from unit rows.",
)
def list_equipment(
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _refuse_attendees(authorization)
    return service.list_equipment()


@router.get(
    "/queue",
    response_model=list[EquipmentReservationOut],
    summary="Reservations waiting for re-verification",
    description="SPM-86. Technical support. Held reservations whose event changed, including a quantity "
    "the extra units cannot cover. Nothing here has been reserved beyond what was already held.",
    responses=error_responses(403),
)
def reverification_queue(
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _technical_support(authorization)
    return service.reverification_queue()


@router.get(
    "/upcoming",
    response_model=list[UpcomingEventOut],
    summary="Upcoming events with equipment requirements",
    description="SPM-4. Technical support. Upcoming events that have equipment requirements, soonest first, "
    "with anything needing attention (including re-verification) ahead of the rest on the same date. "
    "Completed and cancelled events are left out. `state` is `awaiting_review`, `partly_reserved`, "
    "`fully_reserved` or `unavailable`.",
    responses=error_responses(403, 422, 503),
)
def upcoming_events_queue(
    state: str | None = Query(default=None, pattern="^(awaiting_review|partly_reserved|fully_reserved|unavailable)$"),
    dateFrom: date | None = Query(default=None, description="Earliest event date, inclusive."),
    dateTo: date | None = Query(default=None, description="Latest event date, inclusive."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _technical_support(authorization)
    events = fetch_upcoming_events(authorization)
    return service.upcoming_queue(events, fetch_venue_name, state, dateFrom, dateTo)


@router.get(
    "/dashboard",
    response_model=TechDashboardOut,
    summary="Technical support's home screen",
    description="SPM-58. Technical support only, the same as the screens each item opens. Requests awaiting "
    "review, reservations flagged for re-verification, unresolved unavailable or partly fulfilled lines, and "
    "upcoming events with equipment held for them, each soonest first. Only events that have not ended and "
    "are still live are included.",
    responses=error_responses(403, 503),
)
def technical_dashboard(
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _technical_support(authorization)
    return service.technical_dashboard(fetch_upcoming_events(authorization))


def _refuse_attendees(authorization: str | None) -> dict:
    """SPM-127: equipment and an event's arrangements are staff pages, 403 for an attendee."""
    caller = resolve_caller(authorization, settings.user_service_url)
    if caller.get("role") == "attendee":
        raise forbidden("Attendees can open only confirmed event pages and their own registrations.")
    return caller


def _technical_support(authorization: str | None) -> dict:
    return resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})


@router.post(
    "",
    response_model=EquipmentOut,
    status_code=201,
    summary="Add an equipment type",
    description="Technical support only.",
    responses=error_responses(403, 409, 422, 503),
)
def create_equipment(
    body: EquipmentCreate,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.create_equipment(body, caller)


@router.post(
    "/availability",
    summary="Check equipment availability",
    description="With equipmentId, startsAt, and endsAt, returns the quantity free in that period. With eventId, reports each requested line, whether the whole request can be met, and which other events hold overlapping stock. The check does not reserve anything.",
    responses=error_responses(404, 422),
)
def check_availability(body: EquipmentAvailabilityIn, service: EquipmentService = Depends(get_equipment_service)):
    if body.eventId:
        return service.check_event_request(body.eventId)
    if body.equipmentId is None or body.startsAt is None or body.endsAt is None:
        raise HTTPException(status_code=422, detail="equipmentId, startsAt, and endsAt are required")
    return service.check_availability(body)


@router.post(
    "/reservations",
    response_model=EquipmentReservationOut,
    status_code=201,
    summary="Reserve a quantity for a period",
    description="Technical support only. Holds quantity so availability and catalogue edits can see it.",
    responses=error_responses(403, 404, 503),
)
def reserve_quantity(
    body: EquipmentQuantityReserve,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.reserve_quantity(body, caller, authorization)


@router.post(
    "/reservations/{reservation_id}/release",
    response_model=EquipmentReservationOut,
    summary="Release a reservation",
    description="Technical support only. Returns the held quantity to the period.",
    responses=error_responses(403, 404, 409, 503),
)
def release_reservation(
    body: ReservationRelease,
    reservation_id: str = Path(..., description="Reservation id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.release_reservation(reservation_id, caller, body.reason, authorization)


@router.get(
    "/reservations",
    response_model=list[EquipmentReservationOut],
    summary="List an event's reservations",
    description="Technical support and coordinators. Every reservation for the event, at any status.",
    responses=error_responses(403, 503),
)
def list_event_reservations(
    eventId: str = Query(..., min_length=1, description="Event id, e.g. `e1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport", "coordinator"})
    return service.list_event_reservations(eventId)


@router.get("/reservations/summary", response_model=list[EquipmentOutcomeOut])
def reservation_summary(
    eventId: str = Query(..., min_length=1),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _refuse_attendees(authorization)
    if caller.get("role") == "organiser":
        check_event_access(eventId, authorization)  # SPM-47: their own organisation's event only
    return service.outcome_summary(eventId)


@router.post(
    "/reservations/{reservation_id}/reconfirm",
    response_model=EquipmentReservationOut,
    summary="Re-confirm a flagged equipment reservation",
    description="SPM-86. Technical support only. Clears the flag when the held quantity still covers the "
    "event, or when any extra units the event now needs are free. Does not raise the reserved quantity. "
    "When the extra units are unavailable the flag stays and nothing is reserved.",
    responses=error_responses(403, 404, 409),
)
def reconfirm_reservation(
    reservation_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _technical_support(authorization)
    return service.reconfirm_reservation(reservation_id, authorization)


@router.get("/reservations/{reservation_id}", response_model=EquipmentReservationOut)
def get_reservation(
    reservation_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _technical_support(authorization)
    return service.get_reservation(reservation_id)


def _event_releaser(event_id: str, authorization: str | None) -> dict:
    """Coordinators and technical support release an event's stock; so does an organiser cancelling
    their own organisation's event (SPM-88 AC1), which event-service decides (SPM-47)."""
    caller = resolve_caller(
        authorization, settings.user_service_url, allowed_roles={"coordinator", "techsupport", "organiser"}
    )
    if caller.get("role") == "organiser":
        check_event_access(event_id, authorization)
    return caller


@router.post(
    "/reservations/release-for-event",
    response_model=list[ReleasedReservationOut],
    summary="Release every reservation an event holds",
    description="Coordinators, technical support, and the event's own organiser (SPM-88). Rejecting, cancelling, "
    "or completing an event frees its stock. Each reply names the previous status, so the release can be undone, "
    "and the technical support member who handled the line.",
    responses=error_responses(403, 404, 503),
)
def release_holds_for_event(
    body: EventHoldsRelease,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _event_releaser(body.eventId, authorization)
    return service.release_holds_for_event(body.eventId, caller, body.reason)


@router.post(
    "/reservations/restore-for-event",
    response_model=list[EquipmentReservationOut],
    summary="Undo a cancellation's equipment release",
    description="SPM-88 AC9. The same people as the release. Event-service calls it when a cancellation fails "
    "after its equipment release, so the event and its reservations never disagree. Each named reservation of "
    "the event that is still `released` holds its stock again with the status it had.",
    responses=error_responses(403, 404, 503),
)
def restore_holds_for_event(
    body: ReservationRestoreRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _event_releaser(body.eventId, authorization)
    return service.restore_holds_for_event(body.eventId, body.reservations, caller)


@router.post(
    "/reservations/reschedule/preview",
    response_model=list[RescheduledReservationOut],
    summary="Check an event's reservations at a new date and time",
    description="SPM-87 AC2. The event's assigned coordinator only. For each reservation still holding stock, "
    "whether its quantity is free at the new time, with other events' reservations counted and the event's own "
    "left out. Nothing is moved.",
    responses=error_responses(403, 404, 422),
)
def preview_reservation_reschedule(
    body: ReservationReschedulePreview,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    require_assigned_coordinator(
        fetch_event_coordinator(body.eventId, authorization), caller["userId"], "reschedule its equipment"
    )
    return service.preview_reschedule(body)


@router.post(
    "/reservations/reschedule",
    response_model=list[RescheduledReservationOut],
    summary="Move an event's reservations to its new date and time",
    description="SPM-87 AC6. The event's assigned coordinator only; event-service calls it when a reschedule is "
    "applied. Every reservation still holding stock moves to the new time, freeing the old one. Any whose "
    "quantity cannot be met then is flagged for re-verification, not dropped, and technical support are "
    "notified. The event's open equipment requests take the new time too.",
    responses=error_responses(403, 404, 422),
)
def reschedule_reservations(
    body: ReservationReschedule,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    require_assigned_coordinator(
        fetch_event_coordinator(body.eventId, authorization), caller["userId"], "reschedule its equipment"
    )
    return service.reschedule_reservations(body, caller, authorization)


@router.post(
    "/reservations/reverification",
    response_model=list[EquipmentReservationOut],
    summary="Mark an event's reservations for re-verification",
    description="Coordinators and safety officers (SPM-71 AC4, SPM-120). Called by event-service when a "
    "significant event change is saved, or when a safety officer asks for the technical arrangements to be "
    "reviewed again. Each `active` or `reserved` reservation for the event gets `needsReverification` and "
    "the reason; its status is unchanged, so the stock stays held. Returns the reservations marked.",
    responses=error_responses(403, 503),
)
def flag_reservations_for_reverification(
    body: ReservationReverificationRequest,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator", "safety"})
    return service.flag_for_reverification(body.eventId, body.reason, authorization)


@router.get(
    "/requests",
    response_model=list[EquipmentRequestOut],
    summary="List equipment requests",
    description="Technical support and coordinators.",
    responses=error_responses(403, 503),
)
def list_requests(
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    resolve_caller(
        authorization,
        settings.user_service_url,
        allowed_roles={"techsupport", "coordinator"},
    )
    return service.list_requests()


@router.get(
    "/{equipment_id}",
    response_model=EquipmentOut,
    summary="Get equipment",
    responses=error_responses(404),
)
def get_equipment(
    equipment_id: str = Path(..., description="Equipment id, e.g. `eq1`."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _refuse_attendees(authorization)
    return service.get_equipment(equipment_id)


@router.patch(
    "/{equipment_id}",
    response_model=EquipmentOut,
    summary="Edit an equipment type",
    description="Technical support only. Rejects out-of-service counts above the total. Returns 409 when the save cuts into reserved stock unless acknowledgeReservationImpact is true.",
    responses=error_responses(403, 404, 409, 422, 503),
)
def update_equipment(
    body: EquipmentUpdate,
    equipment_id: str = Path(..., description="Equipment id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.update_equipment(equipment_id, body, caller)


@router.get(
    "/{equipment_id}/activity-log",
    response_model=list[EquipmentActivityLogOut],
    summary="Catalogue activity log",
    responses=error_responses(404),
)
def get_activity_log(
    equipment_id: str = Path(..., description="Equipment id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _refuse_attendees(authorization)
    return service.get_activity_log(equipment_id)


@router.get(
    "/{equipment_id}/reservations",
    response_model=list[EquipmentReservationOut],
    summary="List reservations for one equipment type",
    responses=error_responses(404),
)
def list_reservations(
    equipment_id: str = Path(..., description="Equipment id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    _technical_support(authorization)
    return service.list_reservations(equipment_id)


@router.post(
    "/requests",
    response_model=EquipmentRequestOut,
    status_code=201,
    summary="Request equipment",
    description="The event's assigned coordinator only (SPM-46). Creates a request in status `pending`. "
    "`requestedBy` is taken from the bearer token. 404 if the event does not exist.",
    responses=error_responses(403, 404, 503),
)
def create_request(
    body: EquipmentRequestCreate,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    require_assigned_coordinator(
        fetch_event_coordinator(body.eventId, authorization), caller["userId"], "request equipment for it"
    )
    return service.create_request(body, caller["userId"], authorization)


@router.get(
    "/requests/{request_id}",
    response_model=EquipmentRequestOut,
    summary="Open one equipment request",
    description="Technical support and the coordinator can read it. Status stays `pending` until technical support acts.",
    responses=error_responses(403, 404, 503),
)
def get_request(
    request_id: str = Path(..., description="Request id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport", "coordinator"})
    return service.get_request(request_id)


@router.post(
    "/requests/{request_id}/unavailable",
    response_model=EquipmentRequestOut,
    summary="Mark a request unavailable",
    description="Technical support only. Records who acted and when, and queues an email to the coordinator.",
    responses=error_responses(403, 404, 409, 503),
)
def mark_unavailable(
    body: EquipmentRequestUnavailable,
    request_id: str = Path(..., description="Request id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.mark_unavailable(
        request_id, caller, body.reason, body.note, authorization, body.alternativeEquipmentId
    )


@router.post("/requests/{request_id}/partial", response_model=EquipmentRequestOut)
def record_partial(
    body: EquipmentPartialFulfillment,
    request_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.record_partial(request_id, body.reservedQuantity, body.reason, caller, authorization)


@router.post("/requests/{request_id}/accept-shortfall", response_model=EquipmentRequestOut)
def accept_shortfall(
    request_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return service.accept_shortfall(request_id, caller, authorization)


@router.post("/requests/{request_id}/complete-review", response_model=EquipmentRequestOut)
def complete_review(
    request_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.complete_review(request_id, caller)


@router.patch("/reservations/{reservation_id}", response_model=EquipmentReservationOut)
def adjust_reservation(
    body: EquipmentReservationAdjust,
    reservation_id: str,
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = _technical_support(authorization)
    return service.adjust_reservation(reservation_id, body.quantity, caller, authorization)


@router.patch(
    "/requests/{request_id}/details",
    response_model=EquipmentRequestOut,
    summary="Refine a pending equipment request",
    description="The event's assigned coordinator only (SPM-46). Updates quantity and technical requirements "
    "while the request is still `pending`.",
    responses=error_responses(403, 404, 409, 503),
)
def refine_request(
    body: EquipmentRequestRefine,
    request_id: str = Path(..., description="Request id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    event_id = service.get_request(request_id).eventId
    require_assigned_coordinator(
        fetch_event_coordinator(event_id, authorization), caller["userId"], "change its equipment requests"
    )
    return service.refine_request(
        request_id, body.quantity, body.technicalRequirements, caller["userId"], authorization
    )


@router.patch(
    "/requests/{request_id}",
    summary="Direct status edits are refused",
    description="A coordinator cannot set Reserved or Unavailable on this route. Technical support uses review, reserve, and unavailable.",
    responses=error_responses(403, 503),
)
def patch_request_status(
    body: EquipmentRequestStatusPatch,
    request_id: str = Path(..., description="Request id."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    if body.resubmit:
        caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
        return service.amend_request(request_id, body.quantity, caller["userId"], authorization)
    _technical_support(authorization)
    raise forbidden(f"Request {request_id} cannot be set to {body.status} directly")


@router.post(
    "/requests/{request_id}/review",
    response_model=EquipmentRequestOut,
    summary="Review an equipment request",
    description="Technical support only. Sets status to `approved` or `rejected`, and the event's assigned coordinator "
    "is told in the app. Fails with 409 if the request is no longer `pending`.",
    responses=error_responses(403, 404, 409, 503),
)
def review_request(
    body: EquipmentRequestReview,
    request_id: str = Path(..., description="Request id returned by create request."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})
    return service.review_request(request_id, caller["userId"], body.approve, body.reviewNote, authorization)


@router.post(
    "/requests/{request_id}/reserve",
    response_model=EquipmentReservationOut,
    status_code=201,
    summary="Reserve approved equipment",
    description="Technical support only. Request must already be `approved`. Fails with 409 otherwise. The event's "
    "assigned coordinator is told in the app.",
    responses=error_responses(403, 404, 409, 503),
)
def reserve_request(
    request_id: str = Path(..., description="Request id returned by create request."),
    authorization: str | None = Depends(forwarded_bearer),
    service: EquipmentService = Depends(get_equipment_service),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})
    return service.reserve_request(request_id, caller["userId"], authorization)
