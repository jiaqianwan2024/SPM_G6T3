from fastapi import APIRouter, Depends, Header, Query

from app.core.config import settings
from app.routers.user import get_user_service
from app.services.user_service import UserService
from shared.auth.service_key import SERVICE_KEY_HEADER, require_service_key
from shared.openapi import error_responses

# Not behind a user token: callers are other services and scheduled jobs, which
# prove themselves with the service key (SPM-95).
router = APIRouter(
    prefix="/internal/users",
    tags=["internal"],
    responses=error_responses(403),
)


@router.get(
    "",
    summary="Users with the given roles",
    description="Service key only. Just the id and role of everyone holding one of the roles, so a job with no "
    "user token can address notifications to a role.",
)
def users_by_role(
    roles: str = Query(..., description="Comma-separated roles, e.g. `venue,techsupport`."),
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    service: UserService = Depends(get_user_service),
):
    require_service_key(x_service_key, settings.internal_service_key)
    wanted = {role.strip() for role in roles.split(",") if role.strip()}
    return [{"userId": user.userId, "role": user.role} for user in service.list_users() if user.role in wanted]
