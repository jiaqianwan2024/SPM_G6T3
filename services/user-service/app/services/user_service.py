from sqlalchemy.orm import Session

from app.dao.user_dao import UserDAO
from app.models.user import User
from shared.exceptions.http import not_found
from shared.services.base import BaseService

# ConnectSphere's own people, as opposed to its clients (organisers) and the public (attendees).
STAFF_ROLES = frozenset({"coordinator", "coordinatorlead", "venue", "techsupport", "safety"})


class UserService(BaseService):
    def __init__(self, db: Session, user_dao: UserDAO):
        super().__init__(db)
        self.user_dao = user_dao

    def get_by_firebase_claims(self, uid: str, email: str | None) -> User:
        """Resolve a verified Firebase token to a local user.

        Accounts are pre-seeded in this table before their matching Firebase
        account exists, so the first successful login for an email links the
        two by writing firebase_uid onto the existing row.
        """
        user = self.user_dao.get_by_firebase_uid(uid)
        if user:
            return user
        if not email:
            raise not_found("User not found")
        user = self._require(self.user_dao.get_by_email(email), "User not found")
        user.firebaseUid = uid
        self.db.commit()
        return user

    def list_users(self) -> list[User]:
        return self.user_dao.list_all()

    def directory_for(self, caller: User) -> list[User]:
        """The directory as the caller may see it. Staff see everyone. An organiser works for a client
        (SPM-47), so they see ConnectSphere's staff, themselves, and their own organisation's colleagues,
        never attendees or another client's people. Attendees are refused before this (SPM-127)."""
        users = self.list_users()
        if caller.role != "organiser":
            return users
        return [
            user
            for user in users
            if user.role in STAFF_ROLES
            or user.userId == caller.userId
            or (caller.organisationId and user.organisationId == caller.organisationId)
        ]
