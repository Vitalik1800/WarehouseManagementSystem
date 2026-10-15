from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.user_activity_log import UserActivityLog
from backend.app.services.user_activity_log_service import (
    UserActivityLogService
)


PASSWORD = "SecurePassword123!"


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def register_user(client):
    username = f"audit_auth_{uuid4().hex[:16]}"

    response = client.post(
        "/auth/register",
        json={
            "name": "Auth Audit User",
            "username": username,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 201, response.text

    return response.json()["id"], username


def find_activities(db_session, user_id, action):
    db_session.flush()

    statement = select(UserActivityLog).where(
        UserActivityLog.actor_id == user_id,
        UserActivityLog.entity_type == "user",
        UserActivityLog.entity_id == user_id,
        UserActivityLog.action == action,
    )

    return list(db_session.scalars(statement).all())


def test_register_creates_audit(client, db_session):
    user_id, _ = register_user(client)

    activities = find_activities(
        db_session,
        user_id,
        "auth.register",
    )

    assert len(activities) == 1
    assert activities[0].details is None
    assert activities[0].created_at is not None


def test_login_creates_audit(client, db_session):
    user_id, username = register_user(client)

    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["access_token"]

    activities = find_activities(
        db_session,
        user_id,
        "auth.login",
    )

    assert len(activities) == 1
    assert activities[0].details is None


def test_failed_login_does_not_create_audit(client, db_session):
    user_id, username = register_user(client)

    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401

    activities = find_activities(
        db_session,
        user_id,
        "auth.login",
    )

    assert activities == []


def test_logout_creates_audit(client, db_session):
    user_id, username = register_user(client)

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.post(
        "/auth/logout",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 204, response.text

    activities = find_activities(
        db_session,
        user_id,
        "auth.logout",
    )

    assert len(activities) == 1
    assert activities[0].details is None


def test_repeated_logout_does_not_duplicate_audit(
    client,
    db_session,
):
    user_id, username = register_user(client)

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {token}",
    }

    first_response = client.post(
        "/auth/logout",
        headers=headers,
    )

    second_response = client.post(
        "/auth/logout",
        headers=headers,
    )

    assert first_response.status_code == 204
    assert second_response.status_code == 401

    activities = find_activities(
        db_session,
        user_id,
        "auth.logout",
    )

    assert len(activities) == 1


def test_audit_does_not_store_credentials(
    client,
    db_session,
):
    user_id, username = register_user(client)

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    logout_response = client.post(
        "/auth/logout",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert logout_response.status_code == 204

    user = db_session.get(User, user_id)
    assert user is not None

    activities = db_session.scalars(
        select(UserActivityLog).where(
            UserActivityLog.actor_id == user_id,
        )
    ).all()

    assert len(activities) == 3

    for activity in activities:
        assert activity.details is None
        assert PASSWORD not in activity.action
        assert token not in activity.action
        assert user.password_hash not in activity.action


def test_register_audit_error_rolls_back_user(
    client,
    db_session,
):
    username = f"audit_fail_{uuid4().hex[:16]}"

    with patch.object(
        UserActivityLogService,
        "record",
        side_effect=RuntimeError("Audit write failed"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Audit write failed",
        ):
            client.post(
                "/auth/register",
                json={
                    "name": "Rollback Test User",
                    "username": username,
                    "password": PASSWORD,
                },
            )

    user = db_session.scalar(
        select(User).where(
            User.username == username,
        )
    )

    assert user is None


def test_login_audit_error_rolls_back_audit(
    client,
    db_session,
):
    user_id, username = register_user(client)

    with patch.object(
        UserActivityLogService,
        "record",
        side_effect=RuntimeError("Audit write failed"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Audit write failed",
        ):
            client.post(
                "/auth/login",
                json={
                    "username": username,
                    "password": PASSWORD,
                },
            )

    activities = find_activities(
        db_session,
        user_id,
        "auth.login",
    )

    assert activities == []


def test_logout_audit_error_rolls_back_revocation(
    client,
    db_session,
):
    user_id, username = register_user(client)

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": PASSWORD,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    with patch.object(
        UserActivityLogService,
        "record",
        side_effect=RuntimeError("Audit write failed"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Audit write failed",
        ):
            client.post(
                "/auth/logout",
                headers={
                    "Authorization": f"Bearer {token}",
                },
            )

    activities = find_activities(
        db_session,
        user_id,
        "auth.logout",
    )

    assert activities == []

    # The token must remain valid after rollback.
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
