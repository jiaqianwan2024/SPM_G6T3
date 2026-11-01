import logging
from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.sgt import to_sgt
from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.models.attendee_registration import AttendeeRegistration
from app.models.registration_window import RegistrationWindow
from shared.exceptions.http import conflict, forbidden, not_found, unauthorized
from shared.services.base import BaseService

logger = logging.getLogger(__name__)

_CLOSED_EVENT_STATUSES = {"completed", "cancelled"}


def _event(event_id: str, authorization: str | None) -> dict:
    """The event's public page (SPM-127): registering, withdrawing and places left need
    only public facts, and an attendee may not read the full internal event record."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.event_service_url}/events/{event_id}/attendee-card",
                headers={"Authorization": authorization} if authorization else {},
            )
    except httpx.HTTPError as exc:
        raise not_found("Event not found") from exc
    if response.status_code == 403:
        # An attendee may open only confirmed events (or ones they registered for).
        raise conflict("This event has not been confirmed yet.")
    if response.status_code != 200:
        raise not_found("Event not found")
    return response.json()


def _when(raw) -> datetime:
    return datetime.fromisoformat(str(raw).replace("Z", ""))


def _period(opens: datetime, closes: datetime) -> str:
    """The registration period in Singapore time, e.g. "1 Nov 2026 09:00 to 20 Nov 2026 17:00 SGT"."""
    return f"{to_sgt(opens):%d %b %Y %H:%M} to {to_sgt(closes):%d %b %Y %H:%M} SGT"


def eligibility(event: dict, registered_count: int) -> tuple[bool, str | None]:
    now = datetime.utcnow()
    if event.get("status") != "confirmed":
        return False, "This event has not been confirmed yet."
    if not event.get("registrationEnabled"):
        return False, "Registration has not been enabled for this event."
    opens_raw = event.get("registrationOpensAt")
    closes_raw = event.get("registrationClosesAt")
    if not opens_raw or not closes_raw:
        return False, "Registration has not been enabled for this event."
    opens = _when(opens_raw)
    closes = _when(closes_raw)
    # SPM-11 AC6: a refusal outside the period states the period.
    if now < opens:
        return False, f"Registration has not opened yet. The registration period is {_period(opens, closes)}."
    if now > closes:
        return False, f"Registration has closed for this event. The registration period was {_period(opens, closes)}."
    if registered_count >= event["capacity"]:
        return False, "This event is full: it has reached capacity."
    return True, None


def _registration_access(event_id: str, authorization: str | None) -> dict:
    """Ask event-service whether this caller may see the registration list."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.event_service_url}/events/{event_id}/registration-access",
                headers={"Authorization": authorization} if authorization else {},
            )
    except httpx.HTTPError as exc:
        raise not_found("Event not found") from exc
    if response.status_code == 403:
        raise forbidden("You do not have permission to view these registrations.")
    if response.status_code == 401:
        raise unauthorized("Invalid or expired token")
    if response.status_code != 200:
        raise not_found("Event not found")
    return response.json()


def _remaining(capacity: int, registered: int) -> int:
    remaining = capacity - registered
    if remaining < 0:
        remaining = 0
    return remaining


def _owns(row: AttendeeRegistration, caller: dict) -> bool:
    user_id = caller.get("userId") or ""
    email = (caller.get("email") or "").lower()
    if user_id and row.userId and user_id == row.userId:
        return True
    if email and row.attendeeEmail and email == row.attendeeEmail.lower():
        return True
    return False


def withdrawal_unavailable(event: dict) -> str | None:
    """Why this event cannot be withdrawn from, or None when withdrawal is open.

    The start instant itself is closed: an event has started at
    `proposedStartAt`, so withdrawal is only open while now is strictly earlier.
    Completed and cancelled events are closed even when that start is still ahead.
    """
    now = datetime.utcnow()
    status = str(event.get("status") or "").lower()
    if status in _CLOSED_EVENT_STATUSES:
        return "Withdrawal is unavailable because this event has been completed or cancelled."
    start_raw = event.get("proposedStartAt")
    if not start_raw:
        return "Withdrawal is unavailable because this event has no start time."
    start = datetime.fromisoformat(str(start_raw).replace("Z", ""))
    if now >= start:
        return "Withdrawal is unavailable because this event has already started."
    return None


def _report_capacity_reached(event_id: str, authorization: str | None) -> None:
    """SPM-11 AC9: the last place went, so ask event-service to tell the organiser and the
    assigned coordinator. Event-service checks the count itself. Best effort."""
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{settings.event_service_url}/events/{event_id}/capacity-notice",
                headers={"Authorization": authorization} if authorization else {},
            )
    except httpx.HTTPError:
        logger.warning("capacity notice for %s could not be sent", event_id)


class RegistrationService(BaseService):
    def __init__(
        self,
        db: Session,
        registration_dao: AttendeeRegistrationDAO,
        window_dao: RegistrationWindowDAO,
    ):
        super().__init__(db)
        self.registration_dao = registration_dao
        self.window_dao = window_dao

    def list_for_event(self, event_id: str) -> list[AttendeeRegistration]:
        return self.registration_dao.list_for_event(event_id)

    def registered_counts(self, event_ids: list[str]) -> dict[str, int]:
        counts = self.registration_dao.registered_counts(event_ids)
        return {event_id: counts.get(event_id, 0) for event_id in event_ids}

    def registered_count(self, event_id: str) -> int:
        return len(self.list_for_event(event_id))

    def registration_roster(
        self, event_id: str, authorization: str | None, include_withdrawn: bool = True
    ) -> dict:
        access = _registration_access(event_id, authorization)
        if not access.get("registrationEnabled"):
            raise not_found("Registration has not been enabled for this event.")
        rows = self.registration_dao.list_all_for_event(event_id)
        registered = [row for row in rows if row.status == "registered"]
        withdrawn = [row for row in rows if row.status == "withdrawn"]
        capacity = int(access.get("capacity") or 0)
        remaining = _remaining(capacity, len(registered))
        visible = rows if include_withdrawn else registered
        return {
            "eventId": event_id,
            "capacity": capacity,
            "registered": len(registered),
            "withdrawn": len(withdrawn),
            "remaining": remaining,
            "remainingPlaces": remaining,
            "placesRemaining": remaining,
            "registrationOpensAt": access.get("registrationOpensAt"),
            "registrationClosesAt": access.get("registrationClosesAt"),
            "attendees": visible,
        }

    def registration_summary(self, event_id: str, authorization: str | None = None) -> dict:
        event = _event(event_id, authorization)
        return self._summary(event_id, int(event.get("capacity") or 0))

    def attendee_places(self, event_id: str, authorization: str | None) -> dict:
        """Places left for an attendee. Names of other attendees are not included."""
        event = _event(event_id, authorization)
        if not event.get("registrationEnabled"):
            raise not_found("Registration has not been enabled for this event.")
        summary = self._summary(event_id, int(event.get("capacity") or 0))
        summary["registrationOpensAt"] = event.get("registrationOpensAt")
        summary["registrationClosesAt"] = event.get("registrationClosesAt")
        summary["attendees"] = []
        return summary

    def _summary(self, event_id: str, capacity: int) -> dict:
        rows = self.registration_dao.list_all_for_event(event_id)
        registered = [row for row in rows if row.status == "registered"]
        withdrawn = [row for row in rows if row.status == "withdrawn"]
        remaining = _remaining(capacity, len(registered))
        return {
            "eventId": event_id,
            "capacity": capacity,
            "registered": len(registered),
            "withdrawn": len(withdrawn),
            "remaining": remaining,
            "remainingPlaces": remaining,
            "placesRemaining": remaining,
        }

    def list_registrations(self, event_id: str, include_withdrawn: bool = True) -> list[AttendeeRegistration]:
        rows = self.registration_dao.list_all_for_event(event_id)
        if not include_withdrawn:
            return [row for row in rows if row.status == "registered"]
        return rows

    def list_for_attendee(self, email: str) -> list[AttendeeRegistration]:
        return self.registration_dao.list_for_email(email)

    def list_owned(self, user_id: str | None, email: str | None) -> list[AttendeeRegistration]:
        return self.registration_dao.list_owned(user_id, email)

    def get_for_caller(self, registration_id: str, caller: dict) -> AttendeeRegistration:
        return self._owned_row(registration_id, caller)

    def withdraw(self, event_id: str, email: str, authorization: str | None = None) -> AttendeeRegistration:
        current = self.registration_dao.find_for_event_email(event_id, email, status="registered")
        if current is None:
            previous = self.registration_dao.find_for_event_email(event_id, email)
            if previous is not None:
                raise conflict("You are not currently registered for this event.")
            raise not_found("Registration not found")
        return self._withdraw_row(current, authorization)

    def withdraw_for_caller(
        self, registration_id: str, caller: dict, authorization: str | None = None
    ) -> AttendeeRegistration:
        row = self._owned_row(registration_id, caller)
        if row.status != "registered":
            raise conflict("You are not currently registered for this event.")
        return self._withdraw_row(row, authorization)

    def _owned_row(self, registration_id: str, caller: dict) -> AttendeeRegistration:
        row = self._require(self.registration_dao.get(registration_id), "Registration not found")
        if not _owns(row, caller):
            raise forbidden("You do not have permission to use this registration.")
        return row

    def _withdraw_row(self, row: AttendeeRegistration, authorization: str | None) -> AttendeeRegistration:
        event = _event(row.eventId, authorization)
        reason = withdrawal_unavailable(event)
        if reason:
            raise conflict(reason)
        row.status = "withdrawn"
        row.withdrawnAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        # SPM-93 AC5: no notice about the attendee's own withdrawal; the screen confirms it.
        return row

    def register(
        self,
        event_id: str,
        name: str,
        email: str,
        user_id: str | None,
        authorization: str | None = None,
        account_email: str | None = None,
    ) -> AttendeeRegistration:
        """SPM-11. The event's own record decides whether registration is open (AC1, AC6) and
        the event's window row is locked while the places are counted, so two attendees
        sending for the last place are decided one after the other (AC7). Taking the last
        place tells the organiser and coordinator (AC9).

        An attendee registers only themselves: with `account_email` given, the email is the
        account's (it is filled in when left out) and an account holds one registration per
        event (AC5)."""
        email = (email or "").strip() or (account_email or "")
        if account_email and email.lower() != account_email.lower():
            raise forbidden("You can only register yourself, with your account's email address.")
        if not name or not email:
            raise conflict("Name and email are required.")
        event = _event(event_id, authorization)
        ok, reason = eligibility(event, 0)
        if not ok:
            raise conflict(reason)
        self._lock_window(event_id, event)
        existing = self.list_for_event(event_id)
        ok, reason = eligibility(event, len(existing))
        if not ok:
            self.db.rollback()
            raise conflict(reason)
        duplicate = next(
            (
                row
                for row in existing
                if row.attendeeEmail.lower() == email.lower() or (user_id and row.userId == user_id)
            ),
            None,
        )
        if duplicate:
            self.db.rollback()
            raise conflict("You are already registered for this event.")
        row = AttendeeRegistration(
            attendeeRegistrationId=str(uuid4()),
            eventId=event_id,
            attendeeName=name,
            attendeeEmail=email,
            userId=user_id,
            status="registered",
            createdAt=datetime.utcnow(),
        )
        self.registration_dao.add(row)
        self.db.commit()
        self.db.refresh(row)
        # SPM-93 AC5: no notice about the attendee's own registration; the screen confirms it.
        if len(existing) + 1 >= event["capacity"]:
            _report_capacity_reached(event_id, authorization)
        return row

    def _lock_window(self, event_id: str, event: dict) -> RegistrationWindow:
        """The event's window row, locked until the registration commits. Event-service owns
        the period and capacity, so the row is created the first time someone registers and
        refreshed from the event every time. Two first registrations racing to create it are
        settled by the primary key: the loser rolls back and locks the winner's row.

        The transaction that looked for the row always ends before the lock is taken. MySQL's
        REPEATABLE READ fixes a transaction's snapshot at its first plain read, so a count made in
        that same transaction, even after waiting for the lock, would not see a registration the
        lock holder committed meanwhile, and both would get the last place."""
        if self.window_dao.get_for_event(event_id) is None:
            now = datetime.utcnow()
            self.db.add(RegistrationWindow(eventId=event_id, capacity=0, opensAt=now, closesAt=now))
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
        else:
            self.db.commit()
        window = self.window_dao.get_for_event(event_id, lock=True)
        window.capacity = int(event["capacity"])
        window.opensAt = _when(event["registrationOpensAt"])
        window.closesAt = _when(event["registrationClosesAt"])
        return window
