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


def test_register_success_records_activity_and_commits():
    """Checks successful registration and atomic audit recording."""

    db = Mock()
    service = AuthService(db)

    data = UserRegister(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
    )

    user = Mock()
    user.id = 42

    service.users.get_by_username = Mock(return_value=None)
    service.users.create = Mock(return_value=user)
    service.activities.record = Mock()

    result = service.register(data)

    assert result is user

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )

    service.users.create.assert_called_once()

    create_kwargs = service.users.create.call_args.kwargs

    assert create_kwargs["name"] == "Test Worker"
    assert create_kwargs["username"] == "test_worker"
    assert create_kwargs["role"] == "worker"
    assert create_kwargs["password_hash"] != data.password

    service.activities.record.assert_called_once_with(
        action="auth.register",
        actor_id=42,
        entity_type="user",
        entity_id=42,
    )

    db.commit.assert_called_once_with()
    db.rollback.assert_not_called()


def test_register_existing_username_rejected_before_create():
    """Checks early rejection of an already registered username."""

    db = Mock()
    service = AuthService(db)

    data = UserRegister(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
    )

    service.users.get_by_username = Mock(
        return_value=Mock()
    )
    service.users.create = Mock()
    service.activities.record = Mock()

    with pytest.raises(UsernameAlreadyExistsError):
        service.register(data)

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )

    service.users.create.assert_not_called()
    service.activities.record.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
