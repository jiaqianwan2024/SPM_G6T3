"""The notification triggers ConnectSphere publishes (SPM-93).

This registry is the single place that says what each trigger is, who may
receive it, and what the message says. Callers name a trigger and pass the
facts (the context); they never write the message themselves. That keeps every
message plain, names the event (AC7, AC8), and stops one service from
sending another's wording.

Recipient *lookup* stays with the calling service, which already holds the
event, its organiser and its coordinator. Notification-service only checks
that each recipient's role is one this trigger is meant for.
"""

from dataclasses import dataclass

EVENT_LINK = "/app/events/{eventId}"
# Technical support review and reserve an event's equipment on its equipment page.
EQUIPMENT_LINK = "/app/events/{eventId}/equipment"


@dataclass(frozen=True)
class Trigger:
    key: str
    title: str
    body: str
    # Roles that may receive this trigger. A recipient with any other role is a caller bug.
    recipient_roles: frozenset[str]
    # Context values the body needs; a publish without them is rejected.
    required_context: tuple[str, ...] = ("eventName",)
    link: str = EVENT_LINK
    # Sentences added to the body only when the caller sent that context value, as (key, sentence).
    extras: tuple[tuple[str, str], ...] = ()
    # AC9: an attendee can only receive a trigger that is marked attendee-visible.
    attendee_visible: bool = False


_SAFETY_RECIPIENTS = frozenset({"coordinator", "organiser", "venue", "techsupport"})
_EQUIPMENT_RECIPIENTS = frozenset({"coordinator", "organiser"})

TRIGGERS: dict[str, Trigger] = {
    trigger.key: trigger
    for trigger in (
        Trigger(
            key="booking.assigned",
            title="New booking request assigned",
            body="{eventName} has been assigned to you. Open it to review the booking request.",
            recipient_roles=frozenset({"coordinator"}),
        ),
        # An organiser submitted a request. The Lead is told so it can be assigned to a coordinator.
        Trigger(
            key="booking.submitted",
            title="New booking request submitted",
            body="{eventName} was submitted and is waiting to be assigned to a coordinator.",
            recipient_roles=frozenset({"coordinatorlead"}),
        ),
        Trigger(
            key="safety.submitted",
            title="Event details submitted",
            body="The arrangements for {eventName} were submitted to you for a safety review.",
            recipient_roles=frozenset({"safety"}),
        ),
        Trigger(
            key="safety.approved",
            title="Event approved by Safety Officer",
            body="The Safety Officer approved the plan for {eventName}. {note}",
            recipient_roles=_SAFETY_RECIPIENTS,
        ),
        Trigger(
            key="safety.changes_requested",
            title="Safety Officer requests changes",
            body=(
                "The Safety Officer asked for these changes to {eventName}: {reason} "
                "The event is back in planning until it is submitted again."
            ),
            recipient_roles=_SAFETY_RECIPIENTS,
            required_context=("eventName", "reason"),
        ),
        Trigger(
            key="safety.rejected",
            title="Event rejected by Safety Officer",
            body=(
                "The Safety Officer rejected the plan for {eventName}. Reason: {reason} "
                "The event is not cancelled: the coordinator can revise the arrangements "
                "and submit it again."
            ),
            recipient_roles=_SAFETY_RECIPIENTS,
            required_context=("eventName", "reason"),
        ),
        # SPM-70 AC4: the coordinator rejected the request. The organiser reads the reason and explanation.
        Trigger(
            key="event.rejected",
            title="Your request was rejected",
            body="{eventName} was rejected. Reason: {reason}. Explanation: {explanation}",
            recipient_roles=frozenset({"organiser"}),
            required_context=("eventName", "reason", "explanation"),
        ),
        # SPM-87 AC7: the coordinator moved the event. Attendees are told by event-service directly.
        Trigger(
            key="event.rescheduled",
            title="{eventName} has been rescheduled",
            body="{eventName} has moved from {oldPeriod} to {newPeriod}. Reason: {reason}",
            recipient_roles=frozenset({"organiser", "venue", "techsupport"}),
            required_context=("eventName", "oldPeriod", "newPeriod", "reason"),
        ),
        # SPM-78 AC4: a reservation released on a confirmed event. The reason is required,
        # so a release with no reason publishes nothing.
        Trigger(
            key="equipment.released",
            title="Equipment released",
            body="Equipment for {eventName} was released. Reason: {reason}",
            recipient_roles=_EQUIPMENT_RECIPIENTS,
            required_context=("eventName", "reason"),
        ),
        # SPM-6: the organiser answered a clarification. The link opens the event,
        # where the thread is shown. reviewStatus is set only once the request
        # has left review, so the coordinator is not left thinking it still waits.
        Trigger(
            key="clarification.replied",
            title="New reply on {eventName}",
            body="{eventName} ({eventId}) has a new clarification reply: {message}",
            recipient_roles=frozenset({"coordinator"}),
            required_context=("eventName", "eventId", "message"),
            extras=(
                ("reviewStatus", "This request is no longer awaiting review; it is now {reviewStatus}."),
            ),
        ),
        # SPM-77 AC3: a line marked unavailable or only partly fulfilled.
        Trigger(
            key="equipment.shortfall",
            title="Equipment cannot be fully supplied",
            body=(
                "{equipmentName} for {eventName} cannot be fully supplied. "
                "Shortfall: {shortfall}. Reason: {reason}"
            ),
            recipient_roles=frozenset({"coordinator"}),
            required_context=("eventName", "equipmentName", "shortfall", "reason"),
            extras=(("alternative", "Suggested alternative: {alternative}"),),
        ),
        # A coordinator asked for equipment, so technical support know a request is waiting for review.
        Trigger(
            key="equipment.requested",
            title="New equipment request",
            body="{eventName} needs {equipment}. The request is waiting for review.",
            recipient_roles=frozenset({"techsupport"}),
            required_context=("eventName", "equipment"),
            link=EQUIPMENT_LINK,
        ),
        # A coordinator changed a request: refined it, sent it back for review, or accepted its shortfall.
        Trigger(
            key="equipment.request_changed",
            title="Equipment request changed",
            body="The {equipment} request for {eventName} changed: {change}.",
            recipient_roles=frozenset({"techsupport"}),
            required_context=("eventName", "equipment", "change"),
            link=EQUIPMENT_LINK,
        ),
        # SPM-95: a scheduled check finds approaching events whose arrangements are still outstanding.
        Trigger(
            key="readiness.reminder",
            title="Event approaching with arrangements outstanding",
            body="{eventName} is on {eventDate}. Still outstanding: {outstanding}.",
            recipient_roles=frozenset({"coordinator"}),
            required_context=("eventName", "eventDate", "outstanding"),
        ),
        Trigger(
            key="readiness.reminder.venue",
            title="Venue booking still outstanding",
            body="The venue for {eventName} on {eventDate} is still outstanding.",
            recipient_roles=frozenset({"venue"}),
            required_context=("eventName", "eventDate"),
        ),
        Trigger(
            key="readiness.reminder.equipment",
            title="Equipment still outstanding",
            body="The equipment for {eventName} on {eventDate} is still outstanding.",
            recipient_roles=frozenset({"techsupport"}),
            required_context=("eventName", "eventDate"),
        ),
        Trigger(
            key="readiness.reminder.unassigned",
            title="Approaching event has no coordinator",
            body="{eventName} is on {eventDate} and has no coordinator assigned. Still outstanding: {outstanding}.",
            recipient_roles=frozenset({"coordinatorlead"}),
            required_context=("eventName", "eventDate", "outstanding"),
        ),
    )
}


class _Context(dict):
    """Context for str.format_map where an optional value that was not sent renders as nothing."""

    def __missing__(self, key: str) -> str:
        return ""


def render(trigger: Trigger, event_id: str, context: dict[str, str]) -> tuple[str, str, str]:
    """(title, body, link) for one occurrence of the trigger."""
    values = _Context(context)
    body = trigger.body.format_map(values).strip()
    for key, sentence in trigger.extras:
        if str(context.get(key, "")).strip():
            joiner = " " if body[-1] in ".!?" else ". "
            body = f"{body}{joiner}{sentence.format_map(values).strip()}"
    return (
        trigger.title.format_map(values).strip(),
        body,
        trigger.link.format(eventId=event_id),
    )
