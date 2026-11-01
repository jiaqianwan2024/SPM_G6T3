from datetime import datetime
from typing import NamedTuple
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.services.triggers import TRIGGERS, render

# A page large enough that no existing caller that ignores pagination notices
# a behaviour change, while still bounding a single query.
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def send_email(to: str, subject: str, body: str) -> dict:
    print(f"[email] to={to} subject={subject} body={body}")
    return {"channel": "email", "to": to, "status": "queued"}


def _new_row(user_id: str, event_id: str | None, type_: str, title: str, body: str, **extra) -> Notification:
    """`extra` carries the optional published-notification fields: link, resourceType, resourceId, occurrenceId."""
    return Notification(
        notificationId=str(uuid4()),
        userId=user_id,
        eventId=event_id,
        type=type_,
        title=title,
        body=body,
        isRead=False,
        createdAt=datetime.utcnow(),
        **extra,
    )


def record_notification(db: Session, user_id: str, event_id: str | None, type_: str, title: str, body: str) -> Notification:
    """Add a notification for a user. The caller commits."""
    row = _new_row(user_id, event_id, type_, title, body)
    db.add(row)
    return row


def record_notifications_batch(db: Session, items: list[dict]) -> list[Notification]:
    """Add one notification per item in a single round trip.

    This is the fix for the N-sequential-HTTP-calls shape: a caller fanning a
    trigger out to many recipients (e.g. every registered attendee) sends one
    request with the whole recipient list instead of one request per
    recipient, and this does one bulk `add_all` instead of N individual
    inserts. The caller still commits once, same as record_notification.
    """
    rows = [
        _new_row(item["userId"], item.get("eventId"), item["type"], item["title"], item["body"])
        for item in items
    ]
    db.add_all(rows)
    return rows


def list_for_user(
    db: Session,
    user_id: str,
    unread_only: bool = False,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
    bell: bool = False,
) -> list[Notification]:
    query = db.query(Notification).filter(Notification.userId == user_id)
    if bell:
        # The bell panel leaves out what the user cleared; the full history does not.
        query = query.filter(Notification.clearedFromBell.is_(False))
    if unread_only:
        query = query.filter(Notification.isRead.is_(False))
    page = max(page, 1)
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))
    return (
        query.order_by(Notification.createdAt.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )


def count_unread(db: Session, user_id: str) -> int:
    return (
        db.query(Notification)
        .filter(Notification.userId == user_id, Notification.isRead.is_(False))
        .count()
    )


def mark_read(db: Session, user_id: str, notification_id: str) -> Notification | None:
    """Marks one of the caller's own notifications read. Returns None if it
    doesn't exist or belongs to someone else, so the router can 404 either way
    without telling an attacker which case it was."""
    row = (
        db.query(Notification)
        .filter(Notification.notificationId == notification_id, Notification.userId == user_id)
        .first()
    )
    if row is None:
        return None
    row.isRead = True
    return row


def mark_all_read(db: Session, user_id: str) -> int:
    """Returns how many rows were newly marked read (already-read rows don't count)."""
    updated = (
        db.query(Notification)
        .filter(Notification.userId == user_id, Notification.isRead.is_(False))
        .update({"isRead": True}, synchronize_session=False)
    )
    return updated


def clear_all_from_bell(db: Session, user_id: str) -> int:
    """Hides every notification the bell still shows, and marks them read (clearing means seen).
    Nothing is deleted: the full history keeps them. Returns how many rows were cleared."""
    return (
        db.query(Notification)
        .filter(Notification.userId == user_id, Notification.clearedFromBell.is_(False))
        .update({"clearedFromBell": True, "isRead": True}, synchronize_session=False)
    )


def clear_one_from_bell(db: Session, user_id: str, notification_id: str) -> Notification | None:
    """Hides one of the caller's own notifications from the bell and marks it read. None if it is not
    theirs or does not exist (the router 404s either way)."""
    row = (
        db.query(Notification)
        .filter(Notification.notificationId == notification_id, Notification.userId == user_id)
        .first()
    )
    if row is None:
        return None
    row.clearedFromBell = True
    row.isRead = True
    return row


class PublishError(ValueError):
    """The publish request itself is wrong (unknown trigger, missing context, wrong recipient role)."""


class PublishResult(NamedTuple):
    created: int
    skipped_actor: int
    skipped_attendee: int
    skipped_duplicate: int


def publish(
    db: Session,
    trigger_key: str,
    event_id: str,
    occurrence_id: str,
    recipients: list[dict],
    context: dict[str, str],
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> PublishResult:
    """SPM-93: store one notification per recipient for one occurrence of a trigger.

    `recipients` are `{"userId", "role"}` dicts the caller has already worked
    out. A recipient is skipped, not failed, when they are the person who did
    the action (AC5), an attendee on a trigger that is not attendee-visible
    (AC9), listed twice, or already notified for this occurrence (AC6 - which
    also makes a retried call safe). The caller commits.
    """
    trigger = TRIGGERS.get(trigger_key)
    if trigger is None:
        raise PublishError(f"Unknown trigger: {trigger_key}")
    missing = [key for key in trigger.required_context if not str(context.get(key, "")).strip()]
    if missing:
        raise PublishError(f"{trigger_key} needs: {', '.join(missing)}")
    title, body, link = render(trigger, event_id, context)

    skipped_actor = skipped_attendee = skipped_duplicate = 0
    wanted: list[str] = []
    for recipient in recipients:
        user_id, role = recipient["userId"], recipient["role"]
        if user_id == actor_id:
            skipped_actor += 1
        elif role == "attendee" and not trigger.attendee_visible:
            skipped_attendee += 1
        elif role not in trigger.recipient_roles:
            raise PublishError(f"A {role} cannot receive {trigger_key}")
        elif user_id in wanted:
            skipped_duplicate += 1
        else:
            wanted.append(user_id)

    already = set()
    if wanted:
        already = {
            user_id
            for (user_id,) in db.query(Notification.userId).filter(
                Notification.occurrenceId == occurrence_id, Notification.userId.in_(wanted)
            )
        }
    skipped_duplicate += len(already)
    rows = [
        _new_row(
            user_id,
            event_id,
            trigger_key,
            title,
            body,
            link=link,
            resourceType=resource_type,
            resourceId=resource_id,
            occurrenceId=occurrence_id,
        )
        for user_id in wanted
        if user_id not in already
    ]
    db.add_all(rows)
    return PublishResult(len(rows), skipped_actor, skipped_attendee, skipped_duplicate)
