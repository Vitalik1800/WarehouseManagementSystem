from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import User
from backend.app.schemas.users import UserUpdate
from backend.app.services.user_service import (
    UserService,
    UsernameAlreadyExistsError,
    LastActiveAdminError
)

from backend.app.schemas.users import UserRoleUpdate
from backend.app.services.user_service import LastActiveAdminError

from backend.app.services.user_service import UserNotFoundError


def test_update_user_integrity_error_duplicate_username():
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

    competing_user = User(
        id=2,
        name="Competing User",
        username="taken_username",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    service.users.get_by_id = Mock(return_value=user)

    # First lookup: username is available.
    # Second lookup: another transaction has taken it.
    service.users.get_by_username = Mock(
        side_effect=[None, competing_user]
    )

    db.commit.side_effect = IntegrityError(
        statement="UPDATE users SET username = ...",
        params={},
        orig=Exception("Duplicate entry"),
    )

    with pytest.raises(UsernameAlreadyExistsError):
        service.update_user(
            user_id=1,
            data=UserUpdate(username="taken_username"),
        )

    db.commit.assert_called_once()
    db.rollback.assert_called_once()
    db.refresh.assert_not_called()

    service.users.get_by_username.assert_any_call(
        "taken_username"
    )
    assert service.users.get_by_username.call_count == 2


def test_change_user_role_prevents_last_active_admin_demotion():
    db = Mock()
    service = UserService(db)

    admin = User(
        id=1,
        name="Last Administrator",
        username="last_admin",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[admin]
    )
    service.users.get_by_id = Mock(return_value=admin)

    with pytest.raises(LastActiveAdminError):
        service.change_user_role(
            user_id=1,
            data=UserRoleUpdate(role="worker"),
        )

    assert admin.role == "admin"

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_change_user_role_promotes_worker_to_admin():
    db = Mock()
    service = UserService(db)

    worker = User(
        id=2,
        name="Warehouse Worker",
        username="worker",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(return_value=worker)

    result = service.change_user_role(
        user_id=2,
        data=UserRoleUpdate(role="admin"),
    )

    assert result.role == "admin"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(worker)
    db.rollback.assert_not_called()


def test_change_user_role_same_role():
    db = Mock()
    service = UserService(db)

    worker = User(
        id=2,
        name="Warehouse Worker",
        username="worker",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(return_value=worker)

    result = service.change_user_role(
        user_id=2,
        data=UserRoleUpdate(role="worker"),
    )

    assert result.role == "worker"
    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_change_user_role_user_not_found():
    db = Mock()
    service = UserService(db)

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(return_value=None)

    with pytest.raises(UserNotFoundError):
        service.change_user_role(
            user_id=999,
            data=UserRoleUpdate(role="admin"),
        )

    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_change_user_role_demotes_admin_when_another_admin_exists():
    db = Mock()
    service = UserService(db)

    first_admin = User(
        id=1,
        name="First Administrator",
        username="first_admin",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    second_admin = User(
        id=2,
        name="Second Administrator",
        username="second_admin",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[first_admin, second_admin]
    )
    service.users.get_by_id = Mock(
        return_value=first_admin
    )

    result = service.change_user_role(
        user_id=1,
        data=UserRoleUpdate(role="worker"),
    )

    assert result.role == "worker"
    assert second_admin.role == "admin"

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(first_admin)
    db.rollback.assert_not_called()


def test_set_user_active_deactivates_worker():
    db = Mock()
    service = UserService(db)

    worker = User(
        id=2,
        name="Warehouse Worker",
        username="worker",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(
        return_value=worker
    )

    result = service.set_user_active(
        user_id=2,
        is_active=False
    )

    assert result.is_active is False

    service.users.get_active_admins_for_update.assert_called_once()
    service.users.get_by_id.assert_called_once_with(2)

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(worker)
    db.rollback.assert_not_called()


def test_set_user_active_activates_worker():
    db = Mock()
    service = UserService(db)

    worker = User(
        id=2,
        name="Warehouse Worker",
        username="worker",
        password_hash="test_hash",
        role="worker",
        is_active=False,
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(
        return_value=worker
    )

    result = service.set_user_active(
        user_id=2,
        is_active=True,
    )

    assert result.is_active is True

    service.users.get_active_admins_for_update.assert_called_once()
    service.users.get_by_id.assert_called_once_with(2)

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(worker)
    db.rollback.assert_not_called()


def test_set_user_active_prevents_last_admin_deactivation():
    db = Mock()
    service = UserService(db)

    admin = User(
        id=1,
        name="Last Administrator",
        username="last_admin",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[admin]
    )
    service.users.get_by_id = Mock(
        return_value=admin
    )

    with pytest.raises(LastActiveAdminError):
        service.set_user_active(
            user_id=1,
            is_active=False
        )

    assert admin.is_active is True

    service.users.get_active_admins_for_update.assert_called_once()
    service.users.get_by_id.assert_called_once_with(1)

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()


def test_set_user_active_deactivates_admin_when_another_exists():
    db = Mock()
    service = UserService(db)

    first_admin = User(
        id=1,
        name="First Administrator",
        username="first_admin",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    second_admin = User(
        id=2,
        name="Second Administrator",
        username="second_admin",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[first_admin, second_admin]
    )
    service.users.get_by_id = Mock(
        return_value=first_admin
    )

    result = service.set_user_active(
        user_id=1,
        is_active=False
    )

    assert result.is_active is False
    assert first_admin.is_active is False
    assert second_admin.is_active is True
    assert second_admin.role == "admin"

    service.users.get_active_admins_for_update.assert_called_once()
    service.users.get_by_id.assert_called_once_with(1)

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(first_admin)
    db.rollback.assert_not_called()


def test_set_user_active_already_inactive():
    db = Mock()
    service = UserService(db)

    worker = User(
        id=2,
        name="Warehouse Worker",
        username="worker",
        password_hash="test_hash",
        role="worker",
        is_active=False
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(
        return_value=worker
    )

    result = service.set_user_active(
        user_id=2,
        is_active=False
    )

    assert result is worker
    assert result.is_active is False

    service.users.get_active_admins_for_update.assert_called_once()
    service.users.get_by_id.assert_called_once_with(2)

    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_set_user_active_already_active():
    db = Mock()
    service = UserService(db)

    worker = User(
        id=2,
        name="Warehouse Worker",
        username="worker",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(
        return_value=worker
    )

    result = service.set_user_active(
        user_id=2,
        is_active=True
    )

    assert result is worker
    assert result.is_active is True

    service.users.get_active_admins_for_update.assert_called_once()
    service.users.get_by_id.assert_called_once_with(2)

    db.commit.assert_called_once()
    db.refresh.assert_not_called()
    db.rollback.assert_not_called()


def test_set_user_active_user_not_found():
    db = Mock()
    service = UserService(db)

    service.users.get_active_admins_for_update = Mock(
        return_value=[]
    )
    service.users.get_by_id = Mock(
        return_value=None
    )

    with pytest.raises(UserNotFoundError):
        service.set_user_active(
            user_id=999,
            is_active=True
        )

    service.users.get_active_admins_for_update.assert_called_once()
    service.users.get_by_id.assert_called_once_with(999)

    db.commit.assert_not_called()
    db.refresh.assert_not_called()
    db.rollback.assert_called_once()
