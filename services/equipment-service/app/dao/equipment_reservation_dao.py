from app.models.equipment_reservation import EquipmentReservation
from shared.dao.base import BaseDAO

# Reservation statuses that hold units for their event. A partial reservation holds the part
# of a request technical support could cover, so it counts against availability like the others
# and is released with them.
HOLDING_STATUSES = ("active", "reserved", "partial")


class EquipmentReservationDAO(BaseDAO):
    def list_active_for_equipment(self, equipment_id: str) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.equipmentId == equipment_id)
            .filter(EquipmentReservation.status.in_(HOLDING_STATUSES))
            .all()
        )

    def get_by_id(self, reservation_id: str, lock: bool = False) -> EquipmentReservation | None:
        """`lock` reads the latest committed row and holds it until the transaction ends."""
        query = self.db.query(EquipmentReservation).filter(EquipmentReservation.reservationId == reservation_id)
        if lock:
            query = query.with_for_update()
        return query.first()

    def list_for_equipment(self, equipment_id: str) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.equipmentId == equipment_id)
            .all()
        )

    def list_for_event(self, event_id: str) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.eventId == event_id)
            .order_by(EquipmentReservation.startsAt, EquipmentReservation.reservationId)
            .all()
        )

    def list_needing_reverification(self) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.needsReverification.is_(True))
            .filter(EquipmentReservation.status.in_(HOLDING_STATUSES))
            .order_by(EquipmentReservation.startsAt, EquipmentReservation.reservationId)
            .all()
        )

    def list_supplying(self) -> list[EquipmentReservation]:
        """SPM-58: reservations still holding stock for their event, in full or in part."""
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.status.in_(HOLDING_STATUSES))
            .order_by(EquipmentReservation.startsAt, EquipmentReservation.reservationId)
            .all()
        )

    def list_active_for_event(self, event_id: str) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.eventId == event_id)
            .filter(EquipmentReservation.status.in_(HOLDING_STATUSES))
            .order_by(EquipmentReservation.startsAt, EquipmentReservation.reservationId)
            .all()
        )

    def get_by_request_id(self, request_id: str) -> EquipmentReservation | None:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.requestId == request_id)
            .first()
        )
