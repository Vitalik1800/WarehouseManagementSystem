from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import User
from backend.app.schemas.users import UserUpdate
from backend.app.services.user_service import (
    UserService,
    UserNotFoundError,
    UsernameAlreadyExistsError
)


@pytest.fixture
def setup_service():
    db = Mock()
    service = UserService(db)

    user = User(
        id=1,
        name="Original User",
        username="original_user",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    service.users.get_by_id = Mock(return_value=user)
    service.activities.record = Mock()

    return db, service, user


def test_update_user_not_found(setup_service):
    db, service, _ = setup_service
    service.users.get_by_id.return_value = None

    with pytest.raises(UserNotFoundError):
        service.update_user(
            user_id=999,
            data=UserUpdate(name="New Name"),
        )

    service.users.get_by_id.assert_called_once_with(999)
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_update_user_empty_payload(setup_service):
    db, service, user = setup_service

    result = service.update_user(
        user_id=1,
        data=UserUpdate(),
    )

    assert result is user
    service.activities.record.assert_not_called()
    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_update_user_duplicate_username_before_update(setup_service):
    db, service, user = setup_service

    service.users.get_by_username = Mock(
        return_value=Mock()
    )

    with pytest.raises(UsernameAlreadyExistsError):
        service.update_user(
            user_id=1,
            data=UserUpdate(username="taken_username"),
        )

    assert user.username == "original_user"

    service.users.get_by_username.assert_called_once_with(
        "taken_username"
    )
    service.activities.record.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_update_user_success_records_changed_fields(setup_service):
    db, service, user = setup_service

    service.users.get_by_username = Mock(return_value=None)

    result = service.update_user(
        user_id=1,
        data=UserUpdate(
            name="Updated User",
            username="updated_user",
        ),
        actor_id=7,
    )

    assert result is user
    assert user.name == "Updated User"
    assert user.username == "updated_user"

    service.activities.record.assert_called_once_with(
        action="user.updated",
        actor_id=7,
        entity_type="user",
        entity_id=1,
        details={
            "changed_fields": ["name", "username"],
        },
    )

    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(user)
    db.rollback.assert_not_called()


def test_update_user_integrity_error_without_duplicate(setup_service):
    db, service, _ = setup_service

    service.users.get_by_username = Mock(return_value=None)

    error = IntegrityError(
        statement="UPDATE users",
        params={},
        orig=Exception("Other constraint violation"),
    )

    db.commit.side_effect = error

    with pytest.raises(IntegrityError) as exc_info:
        service.update_user(
            user_id=1,
            data=UserUpdate(username="available_username"),
        )

    assert exc_info.value is error
    assert service.users.get_by_username.call_count == 2

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()


def test_update_user_unexpected_error_rolls_back(setup_service):
    db, service, _ = setup_service

    error = RuntimeError("Audit recording failed")
    service.activities.record.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        service.update_user(
            user_id=1,
            data=UserUpdate(name="Updated User"),
        )

    assert exc_info.value is error

    service.activities.record.assert_called_once()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_update_user_unchanged_values_skip_audit(setup_service):
    db, service, user = setup_service

    result = service.update_user(
        user_id=1,
        data=UserUpdate(name="Original User"),
    )

    assert result is user

    service.activities.record.assert_not_called()
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(user)
    db.rollback.assert_not_called()
