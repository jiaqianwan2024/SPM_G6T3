"""Who a published notification goes to (SPM-93 AC3).

Event-service already holds the facts that decide the recipients: the event's
organiser and assigned coordinator, and the user directory for everyone who
is picked by role. This turns a list of audience names into the
`{"userId", "role"}` recipients notification-service expects.
"""

from app.models.event import Event


def people(event: Event, audiences: list[str], directory: dict[str, dict]) -> list[dict]:
    """Recipients for the named audiences.

    "organiser" and "coordinator" are the people on the event itself. Any other
    audience ("venue", "techsupport", "safety") is everyone in the directory
    with that role: nothing ties a venue or technical staff member to one event yet.
    """
    recipients = []
    for audience in audiences:
        if audience == "organiser":
            user_ids = [event.organiserId]
        elif audience == "coordinator":
            user_ids = [event.coordinatorId]
        else:
            user_ids = [user_id for user_id, user in directory.items() if user.get("role") == audience]
        recipients.extend({"userId": user_id, "role": audience} for user_id in user_ids if user_id)
    return recipients
