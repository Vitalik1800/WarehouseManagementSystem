from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.schemas.users import UserCreate

from backend.app.services.user_service import (
    UserService,
    UsernameAlreadyExistsError as UserUsernameAlreadyExistsError
)


def test_create_user_integrity_error_duplicate_username():
    """Checks rollback when username already exists."""

    db = Mock()
    service = UserService(db)

    data = UserCreate(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
        role="worker",
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

    service.activities.record = Mock()

    with pytest.raises(UserUsernameAlreadyExistsError):
        service.create_user(
            data=data,
            actor_id=1,
        )

    assert service.users.get_by_username.call_count == 2

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_create_user_integrity_error_without_duplicate_username():
    """Checks rollback and re-raising an unrelated IntegrityError."""

    db = Mock()
    service = UserService(db)

    data = UserCreate(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
        role="worker",
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
        service.create_user(
            data=data,
            actor_id=1,
        )

    assert exc_info.value is integrity_error

    assert service.users.get_by_username.call_count == 2

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_create_user_unexpected_error_rolls_back():
    """Checks rollback when user creation raises an unexpected error."""

    db = Mock()
    service = UserService(db)

    data = UserCreate(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
        role="worker",
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

    service.activities.record = Mock()

    with pytest.raises(RuntimeError) as exc_info:
        service.create_user(
            data=data,
            actor_id=1,
        )

    assert exc_info.value is unexpected_error

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()
    service.activities.record.assert_not_called()


def test_create_user_success_records_activity_and_commits():
    """Checks successful user creation and atomic audit recording."""

    db = Mock()
    service = UserService(db)

    data = UserCreate(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
        role="worker",
    )

    actor_id = 7

    user = Mock()
    user.id = 42
    user.role = "worker"

    service.users.get_by_username = Mock(return_value=None)
    service.users.create = Mock(return_value=user)
    service.activities.record = Mock()

    result = service.create_user(
        data=data,
        actor_id=actor_id,
    )

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
    assert create_kwargs["password_hash"].startswith("$argon2id$")

    service.activities.record.assert_called_once_with(
        action="user.created",
        actor_id=actor_id,
        entity_type="user",
        entity_id=42,
        details={
            "new_role": "worker"
        },
    )

    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(user)
    db.rollback.assert_not_called()


def test_create_user_existing_username_rejected_before_create():
    """Checks early rejection of an existing username."""

    db = Mock()
    service = UserService(db)

    data = UserCreate(
        name="Test Worker",
        username="test_worker",
        password="SecurePassword123!",
        role="worker",
    )

    service.users.get_by_username = Mock(
        return_value=Mock()
    )
    service.users.create = Mock()
    service.activities.record = Mock()

    with pytest.raises(UserUsernameAlreadyExistsError):
        service.create_user(
            data=data,
            actor_id=7,
        )

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )

    service.users.create.assert_not_called()
    service.activities.record.assert_not_called()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
