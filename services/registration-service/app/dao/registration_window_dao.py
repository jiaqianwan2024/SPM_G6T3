from app.models.registration_window import RegistrationWindow
from shared.dao.base import BaseDAO


class RegistrationWindowDAO(BaseDAO):
    def get_for_event(self, event_id: str, lock: bool = False) -> RegistrationWindow | None:
        """`lock` holds the row (SELECT ... FOR UPDATE) until the transaction ends, so
        registrations for the same event are decided one at a time (SPM-11 AC7)."""
        query = self.db.query(RegistrationWindow).filter(RegistrationWindow.eventId == event_id)
        if lock:
            query = query.with_for_update()
        return query.first()
