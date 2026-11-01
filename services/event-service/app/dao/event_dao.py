from datetime import datetime

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.event import Event
from shared.dao.base import BaseDAO


class EventDAO(BaseDAO):
    def get_by_id(self, event_id: str) -> Event | None:
        return self.db.query(Event).filter(Event.eventId == event_id).first()

    def list_excluding_draft(self) -> list[Event]:
        return self.db.query(Event).filter(Event.status.notin_(["draft", "discarded"])).all()

    def list_excluding_statuses(self, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.status.notin_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_by_status(self, status: str) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.status == status)
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_by_statuses_ordered_by_submitted(self, statuses: list[str]) -> list[Event]:
        """Oldest submittedAt first - i.e. longest-waiting request first."""
        return (
            self.db.query(Event)
            .filter(Event.status.in_(statuses))
            .order_by(Event.submittedAt.asc())
            .all()
        )

    def list_by_statuses_ordered_by_proposed_start(self, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.status.in_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_upcoming_excluding_statuses(self, after: datetime, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.proposedEndAt >= after)
            .filter(Event.status.notin_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_approaching(self, start: datetime, end: datetime, excluding_statuses: list[str]) -> list[Event]:
        """Events that start between `start` and `end` and are not in an excluded status, soonest first."""
        return (
            self.db.query(Event)
            .filter(Event.proposedStartAt >= start, Event.proposedStartAt <= end)
            .filter(Event.status.notin_(excluding_statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_drafts_by_organiser(self, organiser_id: str) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.organiserId == organiser_id, Event.status == "draft")
            .order_by(Event.updatedAt.desc())
            .all()
        )

    def list_organisation_overview(self, organisation_id: str, organiser_id: str) -> list[Event]:
        """SPM-47: a client organisation's events, newest change first, without discarded
        drafts or a colleague's draft (a draft stays with the organiser writing it)."""
        return (
            self.db.query(Event)
            .filter(
                Event.organisationId == organisation_id,
                Event.status != "discarded",
                or_(Event.status != "draft", Event.organiserId == organiser_id),
            )
            .order_by(Event.updatedAt.desc())
            .all()
        )

    def list_by_organiser_excluding_statuses(self, organiser_id: str, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.organiserId == organiser_id, Event.status.notin_(statuses))
            .order_by(Event.updatedAt.desc())
            .all()
        )

    def count_by_coordinator_excluding_statuses(self, statuses: list[str]) -> dict[str, int]:
        """coordinatorId -> how many of their assigned events are not in `statuses`."""
        rows = (
            self.db.query(Event.coordinatorId, func.count(Event.eventId))
            .filter(Event.coordinatorId.isnot(None), Event.status.notin_(statuses))
            .group_by(Event.coordinatorId)
            .all()
        )
        return {coordinator_id: count for coordinator_id, count in rows}

    def list_assigned_excluding_statuses(self, statuses: list[str]) -> list[Event]:
        """Events that have a coordinator and are not in `statuses`, soonest first."""
        return (
            self.db.query(Event)
            .filter(Event.coordinatorId.isnot(None), Event.status.notin_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_by_coordinator_excluding_statuses(self, coordinator_id: str, statuses: list[str]) -> list[Event]:
        """One coordinator's assigned events not in `statuses`, soonest first."""
        return (
            self.db.query(Event)
            .filter(Event.coordinatorId == coordinator_id, Event.status.notin_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def safety_officers(self, event_ids: list[str]) -> dict[str, str | None]:
        """SPM-120: eventId -> the Safety Officer who claimed it, in one query."""
        if not event_ids:
            return {}
        rows = self.db.query(Event.eventId, Event.safetyOfficerId).filter(Event.eventId.in_(event_ids)).all()
        return {event_id: officer_id for event_id, officer_id in rows}

    def claim_safety_review(self, event_id: str, officer_id: str) -> bool:
        """SPM-120: sets the event's Safety Officer only if nobody has claimed it,
        in one UPDATE, so two officers claiming at once cannot both win."""
        claimed = (
            self.db.query(Event)
            .filter(Event.eventId == event_id, Event.safetyOfficerId.is_(None))
            .update({Event.safetyOfficerId: officer_id, Event.updatedAt: datetime.utcnow()}, synchronize_session=False)
        )
        return claimed == 1

    def add(self, row: Event) -> None:
        self.db.add(row)
