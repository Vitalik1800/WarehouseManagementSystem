from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import (
    create_access_token,
    verify_password
)
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.repositories.user_repository import UserRepository

from sqlalchemy import select

from backend.app.models.user_activity_log import UserActivityLog

from unittest.mock import patch

from backend.app.services.user_activity_log_service import (
    UserActivityLogService
)


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


@pytest.fixture
def admin(db_session):
    user = User(
        name="Test Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def worker(db_session):
    user = User(
        name="Test Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def admin_headers(admin):
    token = create_access_token(user_id=admin.id)

    return {
        "Authorization": f"Bearer {token}"
    }


def create_payload(role="worker"):
    return {
        "name": "New Warehouse User",
        "username": f"new_user_{uuid4().hex[:12]}",
        "password": "SecurePassword123!",
        "role": role
    }


@pytest.mark.parametrize("role", ["worker", "admin"])
def test_admin_can_create_user(
    client,
    db_session,
    admin_headers,
    role
):
    payload = create_payload(role)

    response = client.post(
        "/users",
        json=payload,
        headers=admin_headers
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["id"] > 0
    assert data["name"] == payload["name"]
    assert data["username"] == payload["username"]
    assert data["role"] == role
    assert data["is_active"] is True

    assert "password" not in data
    assert "password_hash" not in data

    db_session.expire_all()

    user = UserRepository(db_session).get_by_username(
        payload["username"]
    )

    assert user is not None
    assert user.role == role
    assert user.is_active is True

    assert user.password_hash != payload["password"]
    assert verify_password(
        payload["password"],
        user.password_hash
    )


def test_create_user_defaults_to_worker(
    client,
    db_session,
    admin_headers
):
    payload = create_payload()
    payload.pop("role")

    response = client.post(
        "/users",
        json=payload,
        headers=admin_headers
    )

    assert response.status_code == 201, response.text
    assert response.json()["role"] == "worker"


def test_create_user_without_token(client):
    response = client.post(
        "/users",
        json=create_payload()
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_worker_cannot_create_user(
    client,
    worker
):
    token = create_access_token(user_id=worker.id)

    response = client.post(
        "/users",
        json=create_payload(),
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 403


def test_create_user_duplicate_username(
    client,
    admin_headers,
    admin
):
    payload = create_payload()
    payload["username"] = admin.username

    response = client.post(
        "/users",
        json=payload,
        headers=admin_headers
    )

    assert response.status_code == 409
    assert "detail" in response.json()


@pytest.mark.parametrize(
    "changes",
    [
        {"name": "A"},
        {"name": ""},
        {"username": "ab"},
        {"username": "invalid username"},
        {"password": "short"},
        {"role": "superadmin"},
        {"role": None},
        {"is_active": False},
        {"password_hash": "injected_hash"}
    ]
)
def test_create_user_invalid_payload(
    client,
    admin_headers,
    changes
):
    payload = create_payload()
    payload.update(changes)

    response = client.post(
        "/users",
        json=payload,
        headers=admin_headers
    )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("role", ["worker", "admin"])
def test_create_user_records_audit_event(
    client,
    db_session,
    admin,
    admin_headers,
    role
):
    payload = create_payload(role)

    response = client.post(
        "/users",
        json=payload,
        headers=admin_headers
    )

    assert response.status_code == 201, response.text

    created_user_id = response.json()["id"]

    db_session.expire_all()

    statement = select(UserActivityLog).where(
        UserActivityLog.action == "user.created",
        UserActivityLog.actor_id == admin.id,
        UserActivityLog.entity_type == "user",
        UserActivityLog.entity_id == created_user_id
    )

    audit_event = db_session.scalar(statement)

    assert audit_event is not None
    assert audit_event.details == {
        "new_role": role
    }


def test_create_user_duplicate_does_not_modify_existing_user(
    client,
    db_session,
    admin_headers,
    admin
):
    original_hash = admin.password_hash

    payload = create_payload("admin")
    payload["username"] = admin.username

    response = client.post(
        "/users",
        json=payload,
        headers=admin_headers
    )

    assert response.status_code == 409

    db_session.expire_all()

    existing = db_session.get(User, admin.id)

    assert existing is not None
    assert existing.password_hash == original_hash
    assert existing.role == "admin"
    assert existing.is_active is True


def test_create_user_audit_error_rolls_back_user(
    client,
    db_session,
    admin_headers,
):
    payload = create_payload()
    username = payload["username"]

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
                "/users",
                json=payload,
                headers=admin_headers,
            )

    db_session.expire_all()

    created_user = db_session.scalar(
        select(User).where(
            User.username == username,
        )
    )

    assert created_user is None
