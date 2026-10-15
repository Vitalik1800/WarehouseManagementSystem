from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.user_activity_log import UserActivityLog
from backend.app.services.user_activity_log_service import (
    UserActivityLogService
)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    original = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


def create_user(db_session, *, role="worker", is_active=True):
    user = User(
        name="Audit Rollback User",
        username=f"audit_rollback_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role=role,
        is_active=is_active,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def auth_headers(user):
    return {
        "Authorization": (
            f"Bearer {create_access_token(user_id=user.id)}"
        )
    }


def assert_no_activity(db_session, *, action, entity_id):
    db_session.expire_all()

    activities = list(
        db_session.scalars(
            select(UserActivityLog).where(
                UserActivityLog.action == action,
                UserActivityLog.entity_type == "user",
                UserActivityLog.entity_id == entity_id,
            )
        ).all()
    )

    assert activities == []


def post_audit_failure(client, method, path, headers, json=None):
    with patch.object(
        UserActivityLogService,
        "record",
        side_effect=RuntimeError("Audit write failed"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Audit write failed",
        ):
            client.request(
                method,
                path,
                headers=headers,
                json=json,
            )


def test_update_user_audit_failure_rolls_back(
    client, db_session
):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    worker_id = worker.id
    original_name = worker.name

    post_audit_failure(
        client,
        "PATCH",
        f"/users/{worker_id}",
        auth_headers(admin),
        json={"name": "Should Not Persist"},
    )

    db_session.expire_all()
    stored = db_session.get(User, worker_id)

    assert stored is not None
    assert stored.name == original_name

    assert_no_activity(
        db_session,
        action="user.updated",
        entity_id=worker_id,
    )


def test_change_role_audit_failure_rolls_back(
    client, db_session
):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    worker_id = worker.id

    post_audit_failure(
        client,
        "PATCH",
        f"/users/{worker_id}/role",
        auth_headers(admin),
        json={"role": "admin"},
    )

    db_session.expire_all()
    stored = db_session.get(User, worker_id)

    assert stored is not None
    assert stored.role == "worker"

    assert_no_activity(
        db_session,
        action="user.role_changed",
        entity_id=worker_id,
    )


@pytest.mark.parametrize(
    "initial_active,target_active,endpoint,action",
    [
        (
            False,
            True,
            "activate",
            "user.activated",
        ),
        (
            True,
            False,
            "deactivate",
            "user.deactivated",
        ),
    ],
)
def test_user_status_audit_failure_rolls_back(
    client,
    db_session,
    initial_active,
    target_active,
    endpoint,
    action,
):
    admin = create_user(db_session, role="admin")
    worker = create_user(
        db_session,
        is_active=initial_active,
    )

    worker_id = worker.id

    post_audit_failure(
        client,
        "PATCH",
        f"/users/{worker_id}/{endpoint}",
        auth_headers(admin),
    )

    db_session.expire_all()
    stored = db_session.get(User, worker_id)

    assert stored is not None
    assert stored.is_active == initial_active
    assert stored.is_active != target_active

    assert_no_activity(
        db_session,
        action=action,
        entity_id=worker_id,
    )
