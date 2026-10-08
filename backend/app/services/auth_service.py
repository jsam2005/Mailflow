"""Authentication and user bootstrap services."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User

logger = get_logger(__name__)


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def authenticate(self, email: str, password: str) -> tuple[User, str]:
        user = self.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            logger.info("auth.login_failed", email=email.lower())
            raise UnauthorizedError("Invalid email or password")

        token = create_access_token(user.id, extra_claims={"email": user.email})
        logger.info("auth.login_success", user_id=str(user.id), email=user.email)
        return user, token

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(func.lower(User.email) == email.lower().strip())
        return self.db.scalar(stmt)

    def get_by_id(self, user_id: UUID) -> User | None:
        return self.db.get(User, user_id)

    def ensure_admin_user(self, name: str, email: str, password: str) -> User | None:
        """Create the bootstrap admin if the users table is empty."""
        count = self.db.scalar(select(func.count()).select_from(User)) or 0
        if count > 0:
            return None

        user = User(
            name=name.strip(),
            email=email.lower().strip(),
            password_hash=hash_password(password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info("auth.admin_bootstrapped", user_id=str(user.id), email=user.email)
        return user
