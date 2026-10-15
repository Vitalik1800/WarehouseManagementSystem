from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.security import (
    hash_password,
    verify_password
)
from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository
from backend.app.repositories.revoked_token_repository import (
    RevokedTokenRepository
)
from backend.app.schemas.auth import UserRegister
from backend.app.services.user_activity_log_service import (
    UserActivityLogService
)


_DUMMY_PASSWORD_HASH = hash_password(
    "warehouse_auth_dummy_password"
)


class UsernameAlreadyExistsError(Exception):
    """A user with this username already exists."""


class InvalidCredentialsError(Exception):
    """Invalid username, password, or inactive account."""


class AuthService:
    """Service for registration, authentication, and token revocation."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.revoked_tokens = RevokedTokenRepository(db)
        self.activities = UserActivityLogService(db)

    def register(self, data: UserRegister) -> User:
        """Register a worker and record the event atomically."""
        existing_user = self.users.get_by_username(data.username)

        if existing_user is not None:
            raise UsernameAlreadyExistsError(
                "Користувач із таким логіном уже існує"
            )

        password_hash = hash_password(data.password)

        try:
            user = self.users.create(
                name=data.name,
                username=data.username,
                password_hash=password_hash,
                role="worker"
            )

            self.activities.record(
                action="auth.register",
                actor_id=user.id,
                entity_type="user",
                entity_id=user.id
            )

            self.db.commit()
            return user

        except IntegrityError:
            self.db.rollback()

            if self.users.get_by_username(data.username) is not None:
                raise UsernameAlreadyExistsError(
                    "Користувач із таким логіном уже існує"
                ) from None

            raise

        except Exception:
            self.db.rollback()
            raise

    def authenticate(self, username: str, password: str) -> User:
        """Validate credentials without recording or committing."""
        user = self.users.get_by_username(username)

        password_hash = (
            user.password_hash
            if user is not None
            else _DUMMY_PASSWORD_HASH
        )

        password_valid = verify_password(
            password,
            password_hash
        )

        if (
            user is None
            or not password_valid
            or not user.is_active
        ):
            raise InvalidCredentialsError(
                "Неправильний логін або пароль"
            )

        return user

    def record_successful_login(self, user_id: int) -> None:
        """Persist an audit event after successful JWT generation."""
        try:
            self.activities.record(
                action="auth.login",
                actor_id=user_id,
                entity_type="user",
                entity_id=user_id
            )

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise

    def logout(
        self,
        token_payload: dict,
        actor_id: int | None = None
    ) -> None:
        """Revoke a JWT and record logout in the same transaction."""
        jti = token_payload["jti"]

        expires_at = datetime.fromtimestamp(
            token_payload["exp"],
            tz=timezone.utc
        )

        if self.revoked_tokens.is_revoked(jti):
            return

        try:
            self.revoked_tokens.create(
                jti=jti,
                expires_at=expires_at
            )

            if actor_id is not None:
                self.activities.record(
                    action="auth.logout",
                    actor_id=actor_id,
                    entity_type="user",
                    entity_id=actor_id
                )

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise
