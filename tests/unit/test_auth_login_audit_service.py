from unittest.mock import MagicMock, call

import pytest

from backend.app.services.auth_service import AuthService


@pytest.fixture
def service():
    db = MagicMock()
    auth_service = AuthService(db)
    auth_service.activities = MagicMock()
    return auth_service


def test_successful_login_records_audit_and_commits(service):
    service.record_successful_login(user_id=7)

    service.activities.record.assert_called_once_with(
        action="auth.login",
        actor_id=7,
        entity_type="user",
        entity_id=7,
    )
    service.db.commit.assert_called_once_with()
    service.db.rollback.assert_not_called()


def test_login_audit_error_rolls_back(service):
    error = RuntimeError("Audit recording failed")
    service.activities.record.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        service.record_successful_login(user_id=7)

    assert exc_info.value is error
    service.activities.record.assert_called_once()
    service.db.commit.assert_not_called()
    service.db.rollback.assert_called_once_with()


def test_login_commit_error_rolls_back(service):
    error = RuntimeError("Database commit failed")
    service.db.commit.side_effect = error

    with pytest.raises(RuntimeError) as exc_info:
        service.record_successful_login(user_id=7)

    assert exc_info.value is error
    service.activities.record.assert_called_once_with(
        action="auth.login",
        actor_id=7,
        entity_type="user",
        entity_id=7,
    )
    service.db.commit.assert_called_once_with()
    service.db.rollback.assert_called_once_with()
