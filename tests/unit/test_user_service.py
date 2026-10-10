from unittest.mock import Mock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import User
from backend.app.schemas.users import UserUpdate
from backend.app.services.user_service import (
    UserService,
    UsernameAlreadyExistsError,
)


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
    