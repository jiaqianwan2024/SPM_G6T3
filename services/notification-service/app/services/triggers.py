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
    # AC9: an attendee can only receive a trigger that is marked attendee-visible.
    attendee_visible: bool = False


_SAFETY_RECIPIENTS = frozenset({"coordinator", "organiser", "venue", "techsupport"})

TRIGGERS: dict[str, Trigger] = {
    trigger.key: trigger
    for trigger in (
        Trigger(
            key="booking.assigned",
            title="New booking request assigned",
            body="{eventName} has been assigned to you. Open it to review the booking request.",
            recipient_roles=frozenset({"coordinator"}),
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
    )
}


class _Context(dict):
    """Context for str.format_map where an optional value that was not sent renders as nothing."""

    def __missing__(self, key: str) -> str:
        return ""


def render(trigger: Trigger, event_id: str, context: dict[str, str]) -> tuple[str, str, str]:
    """(title, body, link) for one occurrence of the trigger."""
    values = _Context(context)
    return (
        trigger.title.format_map(values).strip(),
        trigger.body.format_map(values).strip(),
        trigger.link.format(eventId=event_id),
    )
