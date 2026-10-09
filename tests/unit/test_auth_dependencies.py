import pytest
from fastapi import HTTPException

from unittest.mock import Mock, patch

from fastapi.security import HTTPAuthorizationCredentials

from backend.app.api.dependencies.auth import (
    get_current_user,
    get_token_payload
)
from backend.app.core.security import create_access_token
from backend.app.models.user import User

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt

from backend.app.core.config import get_settings


def test_get_current_user_success():
    """Перевіряє отримання активного користувача за дійсним JWT."""

    user = User(
        id=42,
        name="Тестовий користувач",
        username="test_worker",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    token = create_access_token(user_id=user.id)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    db = Mock()

    with (
        patch(
            "backend.app.api.dependencies.auth.RevokedTokenRepository"
        ) as revoked_repository_class,
        patch(
            "backend.app.api.dependencies.auth.UserRepository"
        ) as user_repository_class,
    ):
        revoked_repository = revoked_repository_class.return_value
        revoked_repository.is_revoked.return_value = False

        user_repository = user_repository_class.return_value
        user_repository.get_by_id.return_value = user

        payload = get_token_payload(
            credentials=credentials,
            db=db,
        )

        result = get_current_user(
            payload=payload,
            db=db,
        )

        assert result is user

        assert payload["sub"] == "42"

        revoked_repository_class.assert_called_once_with(db)
        revoked_repository.is_revoked.assert_called_once_with(
            payload["jti"]
        )

        user_repository_class.assert_called_once_with(db)
        user_repository.get_by_id.assert_called_once_with(42)


def test_get_token_payload_missing_token():
    """Перевіряє HTTP 401 за відсутності JWT."""

    db = Mock()

    with pytest.raises(HTTPException) as exc_info:
        get_token_payload(
            credentials=None,
            db=db,
        )

    error = exc_info.value

    assert error.status_code == 401

    assert error.detail == (
        "Не вдалося підтвердити облікові дані"
    )

    assert error.headers == {
        "WWW-Authenticate": "Bearer"
    }


def test_get_token_payload_expired_token():
    """Перевіряє HTTP 401 для простроченого JWT."""

    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload = {
        "sub": "42",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "jti": str(uuid4()),
        "type": "access",
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    db = Mock()

    with patch(
        "backend.app.api.dependencies.auth.RevokedTokenRepository"
    ) as repository_class:

        with pytest.raises(HTTPException) as exc_info:
            get_token_payload(
                credentials=credentials,
                db=db,
            )

        error = exc_info.value

        assert error.status_code == 401

        assert error.detail == (
            "Не вдалося підтвердити облікові дані"
        )

        assert error.headers == {
            "WWW-Authenticate": "Bearer"
        }

        repository_class.assert_not_called()


def test_get_token_payload_invalid_token():
    """Перевіряє HTTP 401 для недійсного JWT."""

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid.jwt.token",
    )

    db = Mock()

    with patch(
        "backend.app.api.dependencies.auth.RevokedTokenRepository"
    ) as repository_class:

        with pytest.raises(HTTPException) as exc_info:
            get_token_payload(
                credentials=credentials,
                db=db,
            )

        error = exc_info.value

        assert error.status_code == 401

        assert error.detail == (
            "Не вдалося підтвердити облікові дані"
        )

        assert error.headers == {
            "WWW-Authenticate": "Bearer"
        }

        repository_class.assert_not_called()


def test_get_current_user_inactive():
    """Перевіряє HTTP 401 для неактивного користувача."""

    user = User(
        id=42,
        name="Неактивний користувач",
        username="inactive_worker",
        password_hash="test_hash",
        role="worker",
        is_active=False,
    )

    token = create_access_token(user_id=user.id)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    db = Mock()

    with (
        patch(
            "backend.app.api.dependencies.auth.RevokedTokenRepository"
        ) as revoked_repository_class,
        patch(
            "backend.app.api.dependencies.auth.UserRepository"
        ) as user_repository_class,
    ):
        revoked_repository = revoked_repository_class.return_value
        revoked_repository.is_revoked.return_value = False

        user_repository = user_repository_class.return_value
        user_repository.get_by_id.return_value = user

        payload = get_token_payload(
            credentials=credentials,
            db=db,
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                payload=payload,
                db=db,
            )

        error = exc_info.value

        assert error.status_code == 401

        assert error.detail == (
            "Не вдалося підтвердити облікові дані"
        )

        assert error.headers == {
            "WWW-Authenticate": "Bearer"
        }

        revoked_repository_class.assert_called_once_with(db)
        revoked_repository.is_revoked.assert_called_once_with(
            payload["jti"]
        )

        user_repository_class.assert_called_once_with(db)
        user_repository.get_by_id.assert_called_once_with(42)


def test_get_current_user_not_found():
    """Перевіряє HTTP 401, якщо користувача більше немає."""

    token = create_access_token(user_id=42)

    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=token,
    )

    db = Mock()

    with (
        patch(
            "backend.app.api.dependencies.auth.RevokedTokenRepository"
        ) as revoked_repository_class,
        patch(
            "backend.app.api.dependencies.auth.UserRepository"
        ) as user_repository_class,
    ):
        revoked_repository = revoked_repository_class.return_value
        revoked_repository.is_revoked.return_value = False

        user_repository = user_repository_class.return_value
        user_repository.get_by_id.return_value = None

        payload = get_token_payload(
            credentials=credentials,
            db=db,
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                payload=payload,
                db=db,
            )

        error = exc_info.value

        assert error.status_code == 401

        assert error.detail == (
            "Не вдалося підтвердити облікові дані"
        )

        assert error.headers == {
            "WWW-Authenticate": "Bearer"
        }

        revoked_repository_class.assert_called_once_with(db)
        revoked_repository.is_revoked.assert_called_once_with(
            payload["jti"]
        )

        user_repository_class.assert_called_once_with(db)
        user_repository.get_by_id.assert_called_once_with(42)