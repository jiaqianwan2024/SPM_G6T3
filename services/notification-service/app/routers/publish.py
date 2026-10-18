from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.services.notifier import PublishError, publish
from shared.auth.service_key import SERVICE_KEY_HEADER, require_service_key
from shared.openapi import error_responses

# Not behind the user-token check in main.py: callers are other services (or a
# scheduled job), which prove themselves with the service key instead.
router = APIRouter(
    prefix="/notifications",
    tags=["notifications"],
    responses=error_responses(403),
)


class PublishRecipient(BaseModel):
    userId: str
    role: str = Field(description="The recipient's role, e.g. organiser, coordinator, venue, techsupport, safety.")


class PublishResource(BaseModel):
    type: str
    id: str


class PublishRequest(BaseModel):
    trigger: str = Field(description="A trigger key from the registry, e.g. booking.assigned.")
    occurrenceId: str = Field(
        min_length=1,
        max_length=128,
        description="Identifies this one occurrence of the trigger. Repeating it never notifies the same user twice.",
    )
    eventId: str
    actorId: str | None = Field(default=None, description="The user who performed the action. They are never notified.")
    recipients: list[PublishRecipient] = Field(max_length=2000)
    context: dict[str, str] = Field(default_factory=dict, description="Facts the message needs, e.g. eventName, reason.")
    resource: PublishResource | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trigger": "booking.assigned",
                "occurrenceId": "e1:booking.assigned:a7",
                "eventId": "e1",
                "actorId": "u-lead",
                "recipients": [{"userId": "u-coord", "role": "coordinator"}],
                "context": {"eventName": "AI in Events Summit"},
            }
        }
    )


class SkippedOut(BaseModel):
    actor: int
    attendeeHidden: int
    duplicate: int


class PublishOut(BaseModel):
    created: int
    skipped: SkippedOut


@router.post(
    "/publish",
    response_model=PublishOut,
    status_code=201,
    summary="Publish one occurrence of a notification trigger",
    description="Stores one notification per recipient. The message is written here from the trigger "
    "registry, not by the caller. The person who did the action, attendees on a trigger that is not "
    "attendee-visible, repeated recipients and recipients already notified for this occurrence are skipped "
    "and counted. Needs the `X-Service-Key` header; a user token is not used.",
)
def publish_notification(
    body: PublishRequest,
    x_service_key: str | None = Header(default=None, alias=SERVICE_KEY_HEADER),
    db: Session = Depends(get_db),
):
    require_service_key(x_service_key, settings.internal_service_key)
    try:
        result = publish(
            db,
            body.trigger,
            body.eventId,
            body.occurrenceId,
            [recipient.model_dump() for recipient in body.recipients],
            body.context,
            actor_id=body.actorId,
            resource_type=body.resource.type if body.resource else None,
            resource_id=body.resource.id if body.resource else None,
        )
    except PublishError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.commit()
    return PublishOut(
        created=result.created,
        skipped=SkippedOut(
            actor=result.skipped_actor,
            attendeeHidden=result.skipped_attendee,
            duplicate=result.skipped_duplicate,
        ),
    )
