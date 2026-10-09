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

_DUMMY_PASSWORD_HASH = hash_password(
    "warehouse_auth_dummy_password"
)


class UsernameAlreadyExistsError(Exception):
    """Користувач із таким логіном уже існує."""


class InvalidCredentialsError(Exception):
    """Неправильний логін, пароль або неактивний обліковий запис."""


class AuthService:
    """Сервіс реєстрації та автентифікації користувачів."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.revoked_tokens = RevokedTokenRepository(db)

    def register(self, data: UserRegister) -> User:
        """Реєструє нового користувача з роллю worker."""
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
        """Перевіряє облікові дані користувача."""
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

    def logout(self, token_payload: dict) -> None:
        """Відкликає JWT, зберігаючи його JTI у базі даних."""
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

            self.db.commit()

        except Exception:
            self.db.rollback()
            raise
