import logging

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.schemas.venue import EventFacts
from shared.exceptions.http import not_found, service_unavailable

EVENT_UNREACHABLE = "The event's details could not be loaded right now. Please try again shortly."


def fetch_event_facts(event_id: str, authorization: str) -> EventFacts:
    """Events live in event-service, so an event's attendance, layout and
    dates are read from there, forwarding the caller's own token."""
    try:
        response = httpx.get(
            f"{settings.event_service_url}/events/{event_id}",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise service_unavailable(EVENT_UNREACHABLE) from exc
    if response.status_code == 404:
        raise not_found("Event not found")
    if response.status_code != 200:
        raise service_unavailable(EVENT_UNREACHABLE)
    return EventFacts.model_validate(response.json())


def find_event_facts(event_id: str, authorization: str) -> EventFacts | None:
    """SPM-108: the calendar still shows a booking whose event cannot be read right now."""
    try:
        return fetch_event_facts(event_id, authorization)
    except HTTPException:
        return None


logger = logging.getLogger("venue.notifications")


def notify_venue_staff(subject: str, body: str, authorization: str, skip_user_id: str | None = None) -> int:
    """SPM-63 AC5 and AC8: email every Venue Staff user through notification-service.

    Best effort: the request itself is already saved, so a notification that
    cannot be sent is logged rather than undoing the coordinator's request.
    Returns how many notifications were accepted. `skip_user_id` leaves out the
    Venue Staff member who took the action themselves.
    """
    try:
        users = httpx.get(
            f"{settings.user_service_url}/users", headers={"Authorization": authorization}, timeout=5.0
        )
        if users.status_code != 200:
            logger.warning("could not list Venue Staff: status %s", users.status_code)
            return 0
        sent = 0
        for user in users.json():
            if user.get("role") != "venue" or (skip_user_id and user.get("userId") == skip_user_id):
                continue
            response = httpx.post(
                f"{settings.notification_service_url}/notifications",
                json={"to": user["email"], "subject": subject, "body": body},
                headers={"Authorization": authorization},
                timeout=5.0,
            )
            if response.status_code == 200:
                sent += 1
            else:
                logger.warning("notification to %s failed: status %s", user["email"], response.status_code)
        return sent
    except httpx.HTTPError as exc:
        logger.warning("could not notify Venue Staff: %r", exc)
        return 0


def notify_role(role: str, event_id: str, title: str, body: str, authorization: str, notice_type: str) -> int:
    """Email a role and put the same notice in each person's in-app inbox. Best effort."""
    try:
        users = httpx.get(
            f"{settings.user_service_url}/users", headers={"Authorization": authorization}, timeout=5.0
        )
        if users.status_code != 200:
            logger.warning("could not list %s: status %s", role, users.status_code)
            return 0
        sent = 0
        for user in users.json():
            if user.get("role") != role:
                continue
            email = httpx.post(
                f"{settings.notification_service_url}/notifications",
                json={"to": user["email"], "subject": title, "body": body},
                headers={"Authorization": authorization},
                timeout=5.0,
            )
            inbox = httpx.post(
                f"{settings.notification_service_url}/notifications/records",
                json={
                    "userId": user["userId"],
                    "eventId": event_id,
                    "type": notice_type,
                    "title": title,
                    "body": body,
                },
                headers={"Authorization": authorization},
                timeout=5.0,
            )
            if email.status_code == 200 or inbox.status_code == 201:
                sent += 1
        return sent
    except httpx.HTTPError as exc:
        logger.warning("could not notify %s: %r", role, exc)
        return 0


def settle_reverification(event_id: str, authorization: str) -> None:
    """Ask event-service whether a reconsidering event can read as confirmed again. Best effort."""
    try:
        httpx.post(
            f"{settings.event_service_url}/events/{event_id}/reverification/settle",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("could not settle re-verification for %s: %r", event_id, exc)


def notify_attendees(event_id: str, change: str, authorization: str) -> None:
    """Ask event-service to tell registered attendees the date, time, or venue changed. Best effort."""
    try:
        httpx.post(
            f"{settings.event_service_url}/events/{event_id}/attendee-notice",
            json={"change": change},
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("could not notify attendees of %s: %r", event_id, exc)


def notify_coordinator(
    user_id: str, event_id: str, title: str, body: str, authorization: str, notice_type: str = "venue.hold"
) -> bool:
    """SPM-116 AC5: put a notification in the coordinator's in-app inbox, through
    notification-service with the Venue Staff member's own token (staff may
    notify another user). Best effort: the hold is already saved."""
    try:
        response = httpx.post(
            f"{settings.notification_service_url}/notifications/records",
            json={"userId": user_id, "eventId": event_id, "type": notice_type, "title": title, "body": body},
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        logger.warning("could not notify coordinator %s: %r", user_id, exc)
        return False
    if response.status_code != 201:
        logger.warning("notification to coordinator %s failed: status %s", user_id, response.status_code)
        return False
    return True
