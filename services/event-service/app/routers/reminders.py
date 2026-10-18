from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.reminders import ReminderRunOut
from app.services.reminders import EventReminders
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.auth.service_key import SERVICE_KEY_HEADER, require_service_key
from shared.openapi import error_responses

# Not behind the user-token check in main.py: the daily job has no user, so it sends the
# service key. A person (a coordinator or the coordinator lead) can run it on demand too.
router = APIRouter(
    prefix="/events/reminders",
    tags=["reminders"],
    responses=error_responses(403),
)


@router.post(
    "/run",
    response_model=ReminderRunOut,
    summary="Run the approaching-event reminder check now",
    description="SPM-95. Finds events starting within the configured lead time (`EVENT_REMINDER_LEAD_DAYS`, "
    "default 7 days) whose readiness still shows an outstanding arrangement, and publishes the reminders. "
    "Callable with the service key (the daily job) or as a coordinator or coordinator lead (on demand, "
    "e.g. in the demo). Safe to repeat: a reminder is raised once per event per start date.",
    responses=error_responses(401, 403),
)
def run_reminders(
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    if x_service_key is not None:
        require_service_key(x_service_key, settings.internal_service_key)
    else:
        resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator", "coordinatorlead"})
    return EventReminders(db).run()
