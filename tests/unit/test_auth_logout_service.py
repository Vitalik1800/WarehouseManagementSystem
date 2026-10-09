import pytest

from datetime import datetime, timezone
from unittest.mock import Mock

from backend.app.services.auth_service import AuthService


def test_logout_success():
    """Перевіряє успішне відкликання JWT."""
    db = Mock()

    service = AuthService(db)

    service.revoked_tokens = Mock()
    service.revoked_tokens.is_revoked.return_value = False

    jti = "550e8400-e29b-41d4-a716-446655440005"
    expiration = 1791633600

    token_payload = {
        "sub": "1",
        "jti": jti,
        "exp": expiration,
        "type": "access"
    }

    result = service.logout(token_payload)

    assert result is None

    service.revoked_tokens.is_revoked.assert_called_once_with(
        jti
    )

    service.revoked_tokens.create.assert_called_once_with(
        jti=jti,
        expires_at=datetime.fromtimestamp(
            expiration,
            tz=timezone.utc
        )
    )

    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


def test_logout_already_revoked():
    """Перевіряє повторний вихід із уже відкликаним JWT."""
    db = Mock()

    service = AuthService(db)

    service.revoked_tokens = Mock()
    service.revoked_tokens.is_revoked.return_value = True

    jti = "550e8400-e29b-41d4-a716-446655440006"

    token_payload = {
        "sub": "1",
        "jti": jti,
        "exp": 1791633600,
        "type": "access"
    }

    result = service.logout(token_payload)

    assert result is None

    service.revoked_tokens.is_revoked.assert_called_once_with(
        jti
    )

    service.revoked_tokens.create.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_logout_rollback_on_create_error():
    """Перевіряє відкат транзакції при помилці відкликання JWT."""
    db = Mock()

    service = AuthService(db)

    service.revoked_tokens = Mock()
    service.revoked_tokens.is_revoked.return_value = False

    service.revoked_tokens.create.side_effect = RuntimeError(
        "Database write failed"
    )

    jti = "550e8400-e29b-41d4-a716-446655440007"

    token_payload = {
        "sub": "1",
        "jti": jti,
        "exp": 1791633600,
        "type": "access"
    }

    with pytest.raises(
        RuntimeError,
        match="Database write failed"
    ):
        service.logout(token_payload)

    service.revoked_tokens.is_revoked.assert_called_once_with(
        jti
    )

    service.revoked_tokens.create.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_called_once_with()


def test_logout_rollback_on_commit_error():
    """Перевіряє відкат транзакції при помилці commit."""
    db = Mock()

    db.commit.side_effect = RuntimeError(
        "Database commit failed"
    )

    service = AuthService(db)

    service.revoked_tokens = Mock()
    service.revoked_tokens.is_revoked.return_value = False

    jti = "550e8400-e29b-41d4-a716-446655440008"

    token_payload = {
        "sub": "1",
        "jti": jti,
        "exp": 1791633600,
        "type": "access"
    }

    with pytest.raises(
        RuntimeError,
        match="Database commit failed"
    ):
        service.logout(token_payload)

    service.revoked_tokens.is_revoked.assert_called_once_with(
        jti
    )

    service.revoked_tokens.create.assert_called_once_with(
        jti=jti,
        expires_at=datetime.fromtimestamp(
            token_payload["exp"],
            tz=timezone.utc
        )
    )

    db.commit.assert_called_once_with()
    db.rollback.assert_called_once_with()
