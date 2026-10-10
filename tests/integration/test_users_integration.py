from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.user import User
from backend.app.core.security import create_access_token


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


def test_list_users_admin_success(client, db_session):
    username = f"admin_{uuid4().hex[:12]}"
    admin = User(
        name="Test Administrator",
        username=username,
        password_hash="test_hash",
        role="admin",
        is_active=True
    )
    db_session.add(admin)
    db_session.flush()

    token = create_access_token(user_id=admin.id)
    response = client.get(
        "/users",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    matching_users = [user for user in data if user["id"] == admin.id]
    assert len(matching_users) == 1
    assert matching_users[0]["username"] == username
    assert matching_users[0]["role"] == "admin"
    assert all("password_hash" not in user for user in data)
    assert all("password" not in user for user in data)


def test_list_users_worker_forbidden(client, db_session):
    worker = User(
        name="Test Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )
    db_session.add(worker)
    db_session.flush()

    token = create_access_token(user_id=worker.id)
    response = client.get(
        "/users",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert "detail" in response.json()
    assert not isinstance(response.json(), list)


def test_list_users_missing_token(client):
    response = client.get("/users")

    assert response.status_code == 401
    assert "detail" in response.json()
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert not isinstance(response.json(), list)


@pytest.mark.parametrize("query", ["offset=-1", "limit=0", "limit=101", "offset=abc", "limit=abc"])
def test_list_users_invalid_pagination(client, db_session, query):
    admin = User(
        name="Pagination Administrator",
        username=f"pagination_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )
    db_session.add(admin)
    db_session.flush()

    token = create_access_token(user_id=admin.id)
    response = client.get(
        f"/users?{query}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_list_users_pagination_success(client, db_session):
    users = [
        User(
            name=f"Pagination User {index}",
            username=f"page_{uuid4().hex[:12]}",
            password_hash="test_hash",
            role="admin" if index == 0 else "worker",
            is_active=True
        )
        for index in range(4)
    ]
    db_session.add_all(users)
    db_session.flush()

    token = create_access_token(user_id=users[0].id)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.get("/users", params={"offset": 0, "limit": 2}, headers=headers)
    second = client.get("/users", params={"offset": 2, "limit": 2}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200

    first_ids = [user["id"] for user in first.json()]
    second_ids = [user["id"] for user in second.json()]

    assert len(first_ids) == 2
    assert len(second_ids) == 2
    assert first_ids == sorted(first_ids)
    assert second_ids == sorted(second_ids)
    assert first_ids[-1] < second_ids[0]
    assert set(first_ids).isdisjoint(second_ids)

def test_get_user_by_id_admin_success(client, db_session):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )
    worker = User(
        name="Warehouse Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    db_session.add_all([admin, worker])
    db_session.flush()

    token = create_access_token(user_id=admin.id)

    response = client.get(
        f"/users/{worker.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.json()
    assert data["id"] == worker.id
    assert data["username"] == worker.username
    assert data["role"] == "worker"
    assert data["is_active"] is True
    assert "password_hash" not in data
    assert "password" not in data


def test_get_user_by_id_not_found(client, db_session):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    db_session.add(admin)
    db_session.flush()

    token = create_access_token(user_id=admin.id)

    response = client.get(
        "/users/2147483647",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


def test_get_user_by_id_worker_forbidden(client, db_session):
    worker = User(
        name="Warehouse Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    db_session.add(worker)
    db_session.flush()

    token = create_access_token(user_id=worker.id)

    response = client.get(
        f"/users/{worker.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_get_user_by_id_missing_token(client):
    response = client.get("/users/1")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("user_id", ["abc", "0", "-1"])
def test_get_user_by_id_invalid_id(client, db_session, user_id):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    db_session.add(admin)
    db_session.flush()

    token = create_access_token(user_id=admin.id)

    response = client.get(
        f"/users/{user_id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422
    