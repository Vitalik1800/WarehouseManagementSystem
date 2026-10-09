from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.auth import UserRegister
from backend.app.services.auth_service import (
    AuthService,
    UsernameAlreadyExistsError,
)


def test_register_integrity_error_duplicate_username():
    """Checks rollback when username already exists."""

    db = Mock()
    service = AuthService(db)

    data = UserRegister(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
    )

    existing_user = Mock()

    service.users.get_by_username = Mock(
        side_effect=[None, existing_user]
    )

    integrity_error = IntegrityError(
        statement="INSERT INTO users",
        params={},
        orig=Exception("Duplicate username"),
    )

    service.users.create = Mock(
        side_effect=integrity_error
    )

    with pytest.raises(UsernameAlreadyExistsError):
        service.register(data)

    assert service.users.get_by_username.call_count == 2

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_register_integrity_error_without_duplicate_username():
    """Checks rollback and re-raising an unrelated IntegrityError."""

    db = Mock()
    service = AuthService(db)

    data = UserRegister(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
    )

    service.users.get_by_username = Mock(
        return_value=None
    )

    integrity_error = IntegrityError(
        statement="INSERT INTO users",
        params={},
        orig=Exception("Database constraint violation"),
    )

    service.users.create = Mock(
        side_effect=integrity_error
    )

    with pytest.raises(IntegrityError) as exc_info:
        service.register(data)

    assert exc_info.value is integrity_error

    assert service.users.get_by_username.call_count == 2

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_register_unexpected_error_rolls_back():
    """Checks rollback when registration raises an unexpected error."""

    db = Mock()
    service = AuthService(db)

    data = UserRegister(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
    )

    service.users.get_by_username = Mock(
        return_value=None
    )

    unexpected_error = RuntimeError(
        "Unexpected database error"
    )

    service.users.create = Mock(
        side_effect=unexpected_error
    )

    with pytest.raises(RuntimeError) as exc_info:
        service.register(data)

    assert exc_info.value is unexpected_error

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
