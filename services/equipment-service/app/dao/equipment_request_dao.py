from app.models.equipment_request import EquipmentRequest
from shared.dao.base import BaseDAO


class EquipmentRequestDAO(BaseDAO):
    def get_by_id(self, request_id: str, lock: bool = False) -> EquipmentRequest | None:
        """`lock` reads the latest committed row and holds it (SELECT ... FOR UPDATE) until the
        transaction ends, so two reservations of the same request are decided one at a time."""
        query = self.db.query(EquipmentRequest).filter(EquipmentRequest.requestId == request_id)
        if lock:
            query = query.with_for_update()
        return query.first()

    def list_all(self) -> list[EquipmentRequest]:
        return self.db.query(EquipmentRequest).order_by(EquipmentRequest.createdAt).all()

    def list_for_event(self, event_id: str) -> list[EquipmentRequest]:
        return (
            self.db.query(EquipmentRequest)
            .filter(EquipmentRequest.eventId == event_id)
            .order_by(EquipmentRequest.createdAt)
            .all()
        )
