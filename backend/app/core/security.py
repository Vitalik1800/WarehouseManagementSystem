from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash

from backend.app.core.config import get_settings


_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Створює захищений хеш пароля за допомогою Argon2id."""
    return _password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """Перевіряє пароль за збереженим хешем."""
    return _password_hash.verify(
        plain_password,
        hashed_password
    )


def create_access_token(user_id: int) -> str:
    """Створює підписаний JWT-токен доступу."""
    if user_id <= 0:
        raise ValueError("Ідентифікатор користувача має бути додатним")

    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.jwt_access_token_expire_minutes
        ),
        "jti": str(uuid4()),
        "type": "access"
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> dict:
    """Перевіряє JWT-токен і повертає його дані."""
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["sub", "iat", "exp", "jti", "type"]
            }
        )

        user_id = payload.get("sub")
        token_id = payload.get("jti")

        if (
            not isinstance(user_id, str)
            or not user_id.isdecimal()
            or int(user_id) <= 0
            or not isinstance(token_id, str)
            or not token_id
            or payload.get("type") != "access"
        ):
            raise InvalidTokenError(
                "Некоректні дані токена доступу"
            )

        return payload

    except InvalidTokenError:
        raise
