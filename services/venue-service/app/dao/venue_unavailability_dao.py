from datetime import datetime

from app.models.venue_unavailability import VenueUnavailability
from shared.dao.base import BaseDAO


class VenueUnavailabilityDAO(BaseDAO):
    def get(self, unavailability_id: str) -> VenueUnavailability | None:
        return self.db.get(VenueUnavailability, unavailability_id)

    def list_for_venue(self, venue_id: str) -> list[VenueUnavailability]:
        return (
            self.db.query(VenueUnavailability)
            .filter(VenueUnavailability.venueId == venue_id)
            .order_by(VenueUnavailability.startsAt, VenueUnavailability.unavailabilityId)
            .all()
        )

    def delete(self, row: VenueUnavailability) -> None:
        self.db.delete(row)

    def find_overlapping(self, venue_id: str, starts_at: datetime, ends_at: datetime) -> list[VenueUnavailability]:
        return (
            self.db.query(VenueUnavailability)
            .filter(VenueUnavailability.venueId == venue_id)
            .filter(VenueUnavailability.startsAt < ends_at)
            .filter(VenueUnavailability.endsAt > starts_at)
            .order_by(VenueUnavailability.startsAt)
            .all()
        )
