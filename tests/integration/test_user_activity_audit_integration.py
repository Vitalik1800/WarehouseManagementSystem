from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.models.user_activity_log import UserActivityLog


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


def create_user(db_session, *, role="worker", is_active=True):
    user = User(
        name="Audit Test User",
        username=f"audit_{uuid4().hex[:16]}",
        password_hash="test_hash",
        role=role,
        is_active=is_active
    )
    db_session.add(user)
    db_session.flush()
    return user


def auth_headers(user):
    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


def find_activities(db_session, *, action, entity_id):
    db_session.flush()

    statement = select(UserActivityLog).where(
        UserActivityLog.action == action,
        UserActivityLog.entity_type == "user",
        UserActivityLog.entity_id == entity_id
    )

    return list(db_session.scalars(statement).all())


def test_update_user_creates_audit_with_admin_actor(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    admin_id = admin.id
    worker_id = worker.id

    response = client.patch(
        f"/users/{worker_id}",
        json={"name": "Updated Audit Worker"},
        headers=auth_headers(admin)
    )

    assert response.status_code == 200, response.text

    activities = find_activities(
        db_session,
        action="user.updated",
        entity_id=worker_id
    )

    assert len(activities) == 1

    activity = activities[0]
    assert activity.actor_id == admin_id
    assert activity.details == {"changed_fields": ["name"]}
    assert activity.created_at is not None


def test_activate_user_creates_audit_with_admin_actor(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session, is_active=False)

    admin_id = admin.id
    worker_id = worker.id

    response = client.patch(
        f"/users/{worker_id}/activate",
        headers=auth_headers(admin)
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is True

    activities = find_activities(
        db_session,
        action="user.activated",
        entity_id=worker_id
    )

    assert len(activities) == 1
    assert activities[0].actor_id == admin_id
    assert activities[0].details == {
        "old_is_active": False,
        "new_is_active": True,
    }


def test_deactivate_user_creates_audit_with_admin_actor(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    admin_id = admin.id
    worker_id = worker.id

    response = client.patch(
        f"/users/{worker_id}/deactivate",
        headers=auth_headers(admin)
    )

    assert response.status_code == 200, response.text
    assert response.json()["is_active"] is False

    activities = find_activities(
        db_session,
        action="user.deactivated",
        entity_id=worker_id
    )

    assert len(activities) == 1
    assert activities[0].actor_id == admin_id
    assert activities[0].details == {
        "old_is_active": True,
        "new_is_active": False
    }


def test_change_role_creates_audit_with_admin_actor(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    admin_id = admin.id
    worker_id = worker.id

    response = client.patch(
        f"/users/{worker_id}/role",
        json={"role": "admin"},
        headers=auth_headers(admin)
    )

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "admin"

    activities = find_activities(
        db_session,
        action="user.role_changed",
        entity_id=worker_id
    )

    assert len(activities) == 1
    assert activities[0].actor_id == admin_id
    assert activities[0].details == {
        "old_role": "worker",
        "new_role": "admin"
    }


def test_update_without_changes_does_not_create_audit(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session)

    worker_id = worker.id
    original_name = worker.name

    response = client.patch(
        f"/users/{worker_id}",
        json={"name": original_name},
        headers=auth_headers(admin)
    )

    assert response.status_code == 200, response.text

    activities = find_activities(
        db_session,
        action="user.updated",
        entity_id=worker_id
    )

    assert activities == []


def test_repeated_activation_does_not_create_audit(client, db_session):
    admin = create_user(db_session, role="admin")
    worker = create_user(db_session, is_active=True)

    worker_id = worker.id

    response = client.patch(
        f"/users/{worker_id}/activate",
        headers=auth_headers(admin)
    )

    assert response.status_code == 200, response.text

    activities = find_activities(
        db_session,
        action="user.activated",
        entity_id=worker_id
    )

    assert activities == []


def test_worker_cannot_update_user_or_create_audit(client, db_session):
    worker = create_user(db_session)
    target = create_user(db_session)

    target_id = target.id

    response = client.patch(
        f"/users/{target_id}",
        json={"name": "Unauthorized Update"},
        headers=auth_headers(worker)
    )

    assert response.status_code == 403

    activities = find_activities(
        db_session,
        action="user.updated",
        entity_id=target_id
    )

    assert activities == []


def test_missing_token_cannot_create_audit(client, db_session):
    target = create_user(db_session)

    target_id = target.id

    response = client.patch(
        f"/users/{target_id}",
        json={"name": "Unauthorized Update"}
    )

    assert response.status_code == 401

    activities = find_activities(
        db_session,
        action="user.updated",
        entity_id=target_id
    )

    assert activities == []
