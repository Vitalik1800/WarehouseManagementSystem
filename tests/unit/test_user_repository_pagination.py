from unittest.mock import Mock

import pytest

from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository


def test_get_all_returns_users():
    db = Mock()

    users = [
        User(id=1, name="Admin", username="admin", role="admin"),
        User(id=2, name="Worker", username="worker", role="worker")
    ]

    db.scalars.return_value.all.return_value = users

    repository = UserRepository(db)

    result = repository.get_all(offset=0, limit=50)

    assert result == users
    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]

    assert statement.compile().params == {
        "param_1": 50,
        "param_2": 0
    }


@pytest.mark.parametrize("offset", [-1, -10])
def test_get_all_rejects_negative_offset(offset):
    db = Mock()
    repository = UserRepository(db)

    with pytest.raises(
        ValueError,
        match="Offset must not be negative"
    ):
        repository.get_all(offset=offset)

    db.scalars.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_get_all_rejects_invalid_limit(limit):
    db = Mock()
    repository = UserRepository(db)

    with pytest.raises(
        ValueError,
        match="Limit must be between 1 and 100"
    ):
        repository.get_all(limit=limit)

    db.scalars.assert_not_called()
