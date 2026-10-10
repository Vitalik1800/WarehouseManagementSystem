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
    

def test_patch_user_admin_success(client, db_session):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )
    worker = User(
        name="Original Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    db_session.add_all([admin, worker])
    db_session.flush()

    token = create_access_token(user_id=admin.id)
    new_username = f"updated_{uuid4().hex[:12]}"

    response = client.patch(
        f"/users/{worker.id}",
        json={
            "name": "Updated Worker",
            "username": new_username
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["id"] == worker.id
    assert data["name"] == "Updated Worker"
    assert data["username"] == new_username
    assert data["role"] == "worker"
    assert data["is_active"] is True
    assert "password_hash" not in data

    db_session.expire_all()
    updated = db_session.get(User, worker.id)

    assert updated.name == "Updated Worker"
    assert updated.username == new_username
    assert updated.role == "worker"
    assert updated.password_hash == "test_hash"


def test_patch_user_not_found(client, db_session):
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

    response = client.patch(
        "/users/2147483647",
        json={"name": "Updated User"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404


def test_patch_user_duplicate_username(client, db_session):
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

    response = client.patch(
        f"/users/{worker.id}",
        json={"username": admin.username},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409
    db_session.refresh(worker)
    assert worker.username != admin.username


def test_patch_user_worker_forbidden(client, db_session):
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

    response = client.patch(
        f"/users/{worker.id}",
        json={"name": "Unauthorized Change"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_patch_user_missing_token(client):
    response = client.patch(
        "/users/1",
        json={"name": "Unauthorized Change"}
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"name": None},
        {"username": None},
        {"name": "A"},
        {"username": "invalid username"},
        {"role": "admin"},
        {"is_active": False},
        {"password_hash": "malicious"}
    ]
)
def test_patch_user_invalid_payload(client, db_session, payload):
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

    response = client.patch(
        f"/users/{admin.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422


def test_patch_user_empty_payload(client, db_session):
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

    response = client.patch(
        f"/users/{admin.id}",
        json={},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["username"] == admin.username


@pytest.mark.parametrize(
    "update_type",
    ["name_only", "username_only", "same_username"]
)
def test_patch_user_partial_update(
    client,
    db_session,
    update_type
):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True
    )

    worker = User(
        name="Original Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True
    )

    db_session.add_all([admin, worker])
    db_session.flush()

    original_name = worker.name
    original_username = worker.username

    if update_type == "name_only":
        payload = {"name": "Updated Name"}
    elif update_type == "username_only":
        payload = {
            "username": f"updated_{uuid4().hex[:12]}"
        }
    else:
        payload = {"username": original_username}

    token = create_access_token(user_id=admin.id)

    response = client.patch(
        f"/users/{worker.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200, response.text

    db_session.expire_all()
    updated = db_session.get(User, worker.id)

    assert updated.name == payload.get(
        "name",
        original_name
    )
    assert updated.username == payload.get(
        "username",
        original_username
    )
    assert updated.role == "worker"
    assert updated.password_hash == "test_hash"


def test_change_user_role_promotes_worker(
    client,
    db_session,
):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    worker = User(
        name="Warehouse Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add_all([admin, worker])
    db_session.flush()

    token = create_access_token(user_id=admin.id)

    response = client.patch(
        f"/users/{worker.id}/role",
        json={"role": "admin"},
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == worker.id
    assert data["role"] == "admin"
    assert data["is_active"] is True
    assert "password_hash" not in data

    db_session.expire_all()

    updated_worker = db_session.get(User, worker.id)

    assert updated_worker is not None
    assert updated_worker.role == "admin"

    updated_admin = db_session.get(User, admin.id)

    assert updated_admin.role == "admin"


def test_change_user_role_prevents_last_active_admin_demotion(
    client,
    db_session,
):
    admin = User(
        name="Last Administrator",
        username=f"last_admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    db_session.add(admin)
    db_session.commit()

    token = create_access_token(user_id=admin.id)

    response = client.patch(
        f"/users/{admin.id}/role",
        json={"role": "worker"},
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 409, response.text
    assert "detail" in response.json()

    db_session.expire_all()

    unchanged_admin = db_session.get(User, admin.id)

    assert unchanged_admin is not None
    assert unchanged_admin.role == "admin"
    assert unchanged_admin.is_active is True


def test_change_user_role_demotes_admin_when_another_exists(
    client,
    db_session,
):
    first_admin = User(
        name="First Administrator",
        username=f"admin_first_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    second_admin = User(
        name="Second Administrator",
        username=f"admin_second_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    db_session.add_all([first_admin, second_admin])
    db_session.commit()

    token = create_access_token(user_id=first_admin.id)

    response = client.patch(
        f"/users/{second_admin.id}/role",
        json={"role": "worker"},
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "worker"

    db_session.expire_all()

    updated_first = db_session.get(User, first_admin.id)
    updated_second = db_session.get(User, second_admin.id)

    assert updated_first is not None
    assert updated_second is not None

    assert updated_first.role == "admin"
    assert updated_first.is_active is True
    assert updated_second.role == "worker"


def test_change_user_role_worker_forbidden(
    client,
    db_session,
):
    worker = User(
        name="Warehouse Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add(worker)
    db_session.commit()

    token = create_access_token(user_id=worker.id)

    response = client.patch(
        f"/users/{worker.id}/role",
        json={"role": "admin"},
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403, response.text

    db_session.expire_all()

    unchanged_worker = db_session.get(User, worker.id)

    assert unchanged_worker is not None
    assert unchanged_worker.role == "worker"


def test_change_user_role_missing_token(client):
    response = client.patch(
        "/users/1/role",
        json={"role": "admin"},
    )

    assert response.status_code == 401


def test_change_user_role_user_not_found(client, db_session):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    db_session.add(admin)
    db_session.commit()

    token = create_access_token(user_id=admin.id)

    response = client.patch(
        "/users/2147483647/role",
        json={"role": "worker"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "superadmin"},
        {"role": "manager"},
        {"role": None},
        {"role": 123},
        {},
    ],
)
def test_change_user_role_invalid_payload(
    client,
    db_session,
    payload,
):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    db_session.add(admin)
    db_session.commit()

    token = create_access_token(user_id=admin.id)

    response = client.patch(
        f"/users/{admin.id}/role",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

    db_session.expire_all()
    unchanged_admin = db_session.get(User, admin.id)

    assert unchanged_admin is not None
    assert unchanged_admin.role == "admin"


def test_change_user_role_same_role(
    client,
    db_session,
):
    admin = User(
        name="Administrator",
        username=f"admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    worker = User(
        name="Warehouse Worker",
        username=f"worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add_all([admin, worker])
    db_session.commit()

    token = create_access_token(user_id=admin.id)

    response = client.patch(
        f"/users/{worker.id}/role",
        json={"role": "worker"},
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == worker.id
    assert data["role"] == "worker"
    assert data["name"] == "Warehouse Worker"
    assert data["is_active"] is True

    db_session.expire_all()

    unchanged_worker = db_session.get(User, worker.id)

    assert unchanged_worker is not None
    assert unchanged_worker.role == "worker"
    assert unchanged_worker.name == "Warehouse Worker"
    assert unchanged_worker.password_hash == "test_hash"
    