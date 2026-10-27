import logging

import httpx

from app.core.config import settings
from shared.auth.service_key import service_key_headers
from shared.exceptions.http import forbidden, not_found, service_unavailable

logger = logging.getLogger("perf.clients")

EVENT_UNREACHABLE = "The event's details could not be loaded right now. Please try again shortly."


def fetch_event_coordinator(event_id: str, authorization: str) -> str | None:
    """SPM-46: events live in event-service, so who is assigned to an event is
    read from there at the moment of each request, forwarding the caller's
    own token. Reading it fresh each time is what makes a reassignment take
    effect immediately."""
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
    return response.json().get("coordinatorId")


def check_event_access(event_id: str, authorization: str | None) -> None:
    """SPM-47: whether the caller may open this event is event-service's rule (an
    organiser opens only their own organisation's events), so ask it with the
    caller's own token and pass on its 403 or 404."""
    try:
        response = httpx.get(
            f"{settings.event_service_url}/events/{event_id}",
            headers={"Authorization": authorization} if authorization else {},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise service_unavailable(EVENT_UNREACHABLE) from exc
    if response.status_code == 403:
        raise forbidden(response.json().get("detail") or "You do not have permission to perform this action")
    if response.status_code == 404:
        raise not_found("Event not found")
    if response.status_code != 200:
        raise service_unavailable(EVENT_UNREACHABLE)


def fetch_upcoming_events(authorization: str) -> list[dict]:
    """SPM-4: events live in event-service, so the upcoming ones are read from there with
    the caller's own token. Event-service already leaves out completed, cancelled,
    rejected and draft events."""
    try:
        response = httpx.get(
            f"{settings.event_service_url}/events/upcoming/technical",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise service_unavailable(EVENT_UNREACHABLE) from exc
    if response.status_code != 200:
        raise service_unavailable(EVENT_UNREACHABLE)
    return response.json()


def fetch_venue_name(event_id: str) -> str:
    """SPM-4: the venue booked for an event, or an empty string when none is booked or
    venue-service cannot be reached. Authenticated with the service key."""
    try:
        response = httpx.get(
            f"{settings.venue_service_url}/internal/venues/bookings/public-summary",
            params={"eventId": event_id},
            headers=service_key_headers(settings.internal_service_key),
            timeout=2.0,
        )
    except httpx.HTTPError:
        return ""
    if response.status_code != 200:
        return ""
    return response.json().get("venueName") or ""


def event_recipients(event: dict, roles: tuple[str, ...]) -> list[dict]:
    """SPM-93: the people on an event record that a trigger is for, as notification
    recipients. `roles` is any of "coordinator" and "organiser"; a role with nobody
    assigned is left out."""
    ids = {"coordinator": event.get("coordinatorId"), "organiser": event.get("organiserId")}
    return [{"userId": ids[role], "role": role} for role in roles if ids.get(role)]


def publish_notification(
    trigger: str,
    event_id: str,
    occurrence_id: str,
    recipients: list[dict],
    context: dict[str, str],
    actor_id: str | None = None,
    resource: dict | None = None,
) -> bool:
    """SPM-93: publish one occurrence of a notification trigger. Notification-service
    writes the message and drops the actor and repeats. Authenticated with the service
    key, not a user token. Best effort: the caller has already saved its change."""
    if not recipients:
        return True
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{settings.notification_service_url}/notifications/publish",
                json={
                    "trigger": trigger,
                    "occurrenceId": occurrence_id,
                    "eventId": event_id,
                    "actorId": actor_id,
                    "recipients": recipients,
                    "context": context,
                    "resource": resource,
                },
                headers=service_key_headers(settings.internal_service_key),
            )
    except httpx.HTTPError as exc:
        logger.warning("publishing %s for %s raised %r", trigger, event_id, exc)
        return False
    if response.status_code != 201:
        logger.warning("publishing %s for %s got status %s", trigger, event_id, response.status_code)
        return False
    return True
