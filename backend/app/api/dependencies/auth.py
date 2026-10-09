from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError
from sqlalchemy.orm import Session

from backend.app.core.security import decode_access_token
from backend.app.db.session import get_db
from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository

from backend.app.repositories.revoked_token_repository import (
    RevokedTokenRepository
)

bearer_scheme = HTTPBearer(auto_error=False)


def get_token_payload(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme)
    ],
    db: Annotated[Session, Depends(get_db)]
) -> dict:
    """Повертає перевірений JWT access token payload."""
    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не вдалося підтвердити облікові дані",
        headers={"WWW-Authenticate": "Bearer"}
    )

    if credentials is None:
        raise authentication_error

    try:
        payload = decode_access_token(
            credentials.credentials
        )

        user_id = int(payload["sub"])

        if user_id <= 0:
            raise ValueError("Invalid user ID")

        jti = payload["jti"]
        expiration = payload["exp"]

        if (
            not isinstance(jti, str)
            or not jti
            or not isinstance(expiration, int)
        ):
            raise ValueError("Invalid JWT claims")

    except (
        InvalidTokenError,
        ValueError,
        TypeError,
        KeyError
    ) as exc:
        raise authentication_error from exc

    revoked_tokens = RevokedTokenRepository(db)

    if revoked_tokens.is_revoked(payload["jti"]):
        raise authentication_error

    return payload


def get_current_user(
    payload: Annotated[
        dict,
        Depends(get_token_payload)
    ],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """Повертає активного користувача за перевіреним JWT."""

    authentication_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не вдалося підтвердити облікові дані",
        headers={"WWW-Authenticate": "Bearer"}
    )

    user_id = int(payload["sub"])

    repository = UserRepository(db)
    user = repository.get_by_id(user_id)

    if user is None or not user.is_active:
        raise authentication_error

    return user
