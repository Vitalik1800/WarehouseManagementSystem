from uuid import uuid4

import pytest
from sqlalchemy import select

from backend.app.core.security import (
    decode_access_token,
    verify_password
)
from backend.app.models.user import User
from backend.app.schemas.auth import UserRegister
from backend.app.services.auth_service import (
    AuthService,
    UsernameAlreadyExistsError
)

from fastapi.testclient import TestClient

from backend.app.db.session import get_db
from backend.app.main import app

from datetime import datetime, timedelta, timezone

import jwt

from backend.app.core.config import get_settings

from backend.app.core.security import create_access_token

from backend.app.core.security import decode_access_token
from backend.app.services.auth_service import AuthService


@pytest.fixture
def client(db_session):
    """Створює HTTP-клієнт з ізольованою сесією MySQL."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_register_user(db_session):
    """Перевіряє створення користувача через AuthService."""
    username = f"register_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    registration_data = UserRegister(
        name="Тестовий користувач",
        username=username,
        password=password,
    )

    service = AuthService(db_session)
    user = service.register(registration_data)

    assert user.id is not None
    assert user.name == "Тестовий користувач"
    assert user.username == username
    assert user.role == "worker"
    assert user.is_active is True

    assert user.password_hash != password
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password(password, user.password_hash)

    saved_user = db_session.scalar(
        select(User).where(User.username == username)
    )

    assert saved_user is not None
    assert saved_user.id == user.id


def test_register_duplicate_username(db_session):
    """Перевіряє заборону повторної реєстрації логіна."""
    username = f"duplicate_{uuid4().hex[:12]}"

    service = AuthService(db_session)

    first_user = UserRegister(
        name="Перший користувач",
        username=username,
        password="FirstPassword123!",
    )

    second_user = UserRegister(
        name="Другий користувач",
        username=username,
        password="SecondPassword123!",
    )

    service.register(first_user)

    with pytest.raises(
        UsernameAlreadyExistsError,
        match="Користувач із таким логіном уже існує",
    ):
        service.register(second_user)

    users = db_session.scalars(
        select(User).where(User.username == username)
    ).all()

    assert len(users) == 1
    assert users[0].name == "Перший користувач"


def test_register_api_success(client, db_session):
    """Перевіряє успішну реєстрацію через HTTP."""
    username = f"api_register_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    response = client.post(
        "/auth/register",
        json={
            "name": "Новий користувач",
            "username": username,
            "password": password,
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] > 0
    assert data["name"] == "Новий користувач"
    assert data["username"] == username
    assert data["role"] == "worker"
    assert data["is_active"] is True

    assert "password" not in data
    assert "password_hash" not in data

    saved_user = db_session.scalar(
        select(User).where(User.username == username)
    )

    assert saved_user is not None
    assert verify_password(
        password,
        saved_user.password_hash,
    )


def test_register_api_duplicate_username(client, db_session):
    """Перевіряє HTTP 409 для вже зайнятого логіна."""
    username = f"api_duplicate_{uuid4().hex[:12]}"

    first_response = client.post(
        "/auth/register",
        json={
            "name": "Перший користувач",
            "username": username,
            "password": "FirstPassword123!",
        },
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/auth/register",
        json={
            "name": "Другий користувач",
            "username": username,
            "password": "SecondPassword123!",
        },
    )

    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Користувач із таким логіном уже існує"
    }

    users = db_session.scalars(
        select(User).where(User.username == username)
    ).all()

    assert len(users) == 1
    assert users[0].name == "Перший користувач"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "name": "А",
            "username": "valid_user",
            "password": "SecurePassword123!",
        },
        {
            "name": "Тестовий користувач",
            "username": "ab",
            "password": "SecurePassword123!",
        },
        {
            "name": "Тестовий користувач",
            "username": "invalid-user!",
            "password": "SecurePassword123!",
        },
        {
            "name": "Тестовий користувач",
            "username": "valid_user",
            "password": "1234567",
        },
        {
            "name": "Тестовий користувач",
            "username": "valid_user",
        },
    ],
    ids=[
        "empty_payload",
        "short_name",
        "short_username",
        "invalid_username_characters",
        "short_password",
        "missing_password",
    ],
)
def test_register_api_invalid_data(client, payload):
    """Перевіряє HTTP 422 для некоректних даних."""
    response = client.post(
        "/auth/register",
        json=payload,
    )

    assert response.status_code == 422

    data = response.json()

    assert "detail" in data
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0


def test_login_api_success(client, db_session):
    """Перевіряє успішний вхід та видачу JWT-токена."""
    username = f"api_login_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    registration_response = client.post(
        "/auth/register",
        json={
            "name": "Користувач для входу",
            "username": username,
            "password": password,
        },
    )

    assert registration_response.status_code == 201

    user_id = registration_response.json()["id"]

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )

    assert login_response.status_code == 200

    data = login_response.json()

    assert data["token_type"] == "bearer"
    assert isinstance(data["access_token"], str)
    assert data["access_token"]

    payload = decode_access_token(data["access_token"])

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "iat" in payload
    assert "exp" in payload
    assert "jti" in payload


def test_login_api_invalid_password(client):
    """Перевіряє HTTP 401 для неправильного пароля."""
    username = f"api_login_wrong_{uuid4().hex[:12]}"

    registration_response = client.post(
        "/auth/register",
        json={
            "name": "Користувач для перевірки",
            "username": username,
            "password": "CorrectPassword123!",
        },
    )

    assert registration_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "WrongPassword123!",
        },
    )

    assert login_response.status_code == 401

    assert login_response.json() == {
        "detail": "Неправильний логін або пароль"
    }

    assert login_response.headers["www-authenticate"] == "Bearer"

    assert "access_token" not in login_response.json()


def test_login_api_nonexistent_user(client):
    """Перевіряє HTTP 401 для неіснуючого користувача."""
    username = f"unknown_login_{uuid4().hex[:12]}"

    response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "SomePassword123!",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Неправильний логін або пароль"
    }

    assert response.headers["www-authenticate"] == "Bearer"

    assert "access_token" not in response.json()


def test_login_api_inactive_user(client, db_session):
    """Перевіряє HTTP 401 для неактивного користувача."""
    username = f"api_inactive_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    registration_response = client.post(
        "/auth/register",
        json={
            "name": "Неактивний користувач",
            "username": username,
            "password": password,
        },
    )

    assert registration_response.status_code == 201

    user = db_session.scalar(
        select(User).where(User.username == username)
    )

    assert user is not None

    user.is_active = False
    db_session.flush()

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )

    assert login_response.status_code == 401

    assert login_response.json() == {
        "detail": "Неправильний логін або пароль"
    }

    assert login_response.headers["www-authenticate"] == "Bearer"

    assert "access_token" not in login_response.json()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {
            "password": "SecurePassword123!",
        },
        {
            "username": "test_worker",
        },
        {
            "username": "",
            "password": "SecurePassword123!",
        },
        {
            "username": "test_worker",
            "password": "",
        },
        {
            "username": "a" * 51,
            "password": "SecurePassword123!",
        },
    ],
    ids=[
        "empty_payload",
        "missing_username",
        "missing_password",
        "empty_username",
        "empty_password",
        "username_too_long",
    ],
)
def test_login_api_invalid_data(client, payload):
    """Перевіряє HTTP 422 для некоректних даних входу."""
    response = client.post(
        "/auth/login",
        json=payload,
    )

    assert response.status_code == 422

    data = response.json()

    assert "detail" in data
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0
    assert "access_token" not in data


def test_get_me_api_success(client):
    """Перевіряє отримання поточного користувача за JWT."""
    username = f"api_me_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    registration_response = client.post(
        "/auth/register",
        json={
            "name": "Тестовий працівник",
            "username": username,
            "password": password,
        },
    )

    assert registration_response.status_code == 201
    registered_user = registration_response.json()

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )

    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "id": registered_user["id"],
        "name": "Тестовий працівник",
        "username": username,
        "role": "worker",
        "is_active": True,
    }

    assert "password" not in response.json()
    assert "password_hash" not in response.json()


def test_get_me_api_missing_token(client):
    """Перевіряє HTTP 401 без заголовка Authorization."""
    response = client.get("/auth/me")

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Не вдалося підтвердити облікові дані"
    }

    assert response.headers["www-authenticate"] == "Bearer"


def test_get_me_api_invalid_token(client):
    """Перевіряє HTTP 401 для недійсного JWT."""
    response = client.get(
        "/auth/me",
        headers={
            "Authorization": "Bearer invalid.jwt.token",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Не вдалося підтвердити облікові дані"
    }

    assert response.headers["www-authenticate"] == "Bearer"

    assert "id" not in response.json()
    assert "username" not in response.json()


def test_get_me_api_expired_token(client):
    """Перевіряє HTTP 401 для простроченого JWT."""
    settings = get_settings()
    now = datetime.now(timezone.utc)

    payload = {
        "sub": "42",
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "jti": str(uuid4()),
        "type": "access",
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Не вдалося підтвердити облікові дані"
    }

    assert response.headers["www-authenticate"] == "Bearer"

    assert "id" not in response.json()
    assert "username" not in response.json()


def test_get_me_api_inactive_user(client, db_session):
    """Перевіряє HTTP 401 після деактивації користувача."""
    username = f"api_me_inactive_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    registration_response = client.post(
        "/auth/register",
        json={
            "name": "Неактивний працівник",
            "username": username,
            "password": password,
        },
    )

    assert registration_response.status_code == 201
    user_id = registration_response.json()["id"]

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": password,
        },
    )

    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    user = db_session.get(User, user_id)

    assert user is not None
    assert user.is_active is True

    user.is_active = False
    db_session.flush()

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Не вдалося підтвердити облікові дані"
    }

    assert response.headers["www-authenticate"] == "Bearer"

    assert "id" not in response.json()
    assert "username" not in response.json()


def test_get_me_api_user_not_found(client, db_session):
    """Перевіряє HTTP 401 для JWT неіснуючого користувача."""
    from sqlalchemy import func, select

    max_user_id = db_session.scalar(
        select(func.max(User.id))
    )

    nonexistent_user_id = (max_user_id or 0) + 1

    assert db_session.get(User, nonexistent_user_id) is None

    access_token = create_access_token(
        user_id=nonexistent_user_id
    )

    response = client.get(
        "/auth/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "Не вдалося підтвердити облікові дані"
    }

    assert response.headers["www-authenticate"] == "Bearer"

    assert "id" not in response.json()
    assert "username" not in response.json()



def test_get_me_api_revoked_token(client, db_session):
    """Перевіряє відхилення відкликаного JWT."""

    username = f"revoked_{uuid4().hex[:12]}"

    register_response = client.post(
        "/auth/register",
        json={
            "name": "Revoked Token User",
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response_before_logout = client.get(
        "/auth/me",
        headers=headers
    )

    assert response_before_logout.status_code == 200

    payload = decode_access_token(access_token)

    service = AuthService(db_session)
    service.logout(payload)

    response_after_logout = client.get(
        "/auth/me",
        headers=headers
    )

    assert response_after_logout.status_code == 401

    assert response_after_logout.json()["detail"] == (
        "Не вдалося підтвердити облікові дані"
    )

    assert response_after_logout.headers["WWW-Authenticate"] == (
        "Bearer"
    )


def test_logout_api_success(client):
    """Перевіряє успішний вихід користувача через API."""

    username = f"logout_{uuid4().hex[:12]}"

    register_response = client.post(
        "/auth/register",
        json={
            "name": "Logout Test User",
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    response_before_logout = client.get(
        "/auth/me",
        headers=headers
    )

    assert response_before_logout.status_code == 200

    logout_response = client.post(
        "/auth/logout",
        headers=headers
    )

    assert logout_response.status_code == 204
    assert logout_response.content == b""

    response_after_logout = client.get(
        "/auth/me",
        headers=headers
    )

    assert response_after_logout.status_code == 401

    assert response_after_logout.json()["detail"] == (
        "Не вдалося підтвердити облікові дані"
    )

    assert response_after_logout.headers["WWW-Authenticate"] == (
        "Bearer"
    )


def test_logout_api_missing_token(client):
    """Перевіряє вихід із системи без JWT."""

    response = client.post("/auth/logout")

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Не вдалося підтвердити облікові дані"
    )

    assert response.headers["WWW-Authenticate"] == (
        "Bearer"
    )


def test_logout_api_invalid_token(client):
    """Перевіряє вихід із системи з недійсним JWT."""

    response = client.post(
        "/auth/logout",
        headers={
            "Authorization": "Bearer invalid.jwt.token"
        }
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Не вдалося підтвердити облікові дані"
    )

    assert response.headers["WWW-Authenticate"] == (
        "Bearer"
    )


def test_logout_api_already_revoked_token(client):
    """Перевіряє повторний logout із відкликаним JWT."""

    username = f"logout_repeat_{uuid4().hex[:12]}"

    register_response = client.post(
        "/auth/register",
        json={
            "name": "Repeat Logout User",
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    first_logout = client.post(
        "/auth/logout",
        headers=headers
    )

    assert first_logout.status_code == 204

    second_logout = client.post(
        "/auth/logout",
        headers=headers
    )

    assert second_logout.status_code == 401

    assert second_logout.json()["detail"] == (
        "Не вдалося підтвердити облікові дані"
    )

    assert second_logout.headers["WWW-Authenticate"] == (
        "Bearer"
    )


def test_logout_api_expired_token(client):
    """Перевіряє відхилення простроченого JWT під час logout."""
    from datetime import datetime, timedelta, timezone

    import jwt

    from backend.app.core.config import get_settings

    settings = get_settings()

    now = datetime.now(timezone.utc)

    payload = {
        "sub": "1",
        "iat": int((now - timedelta(hours=2)).timestamp()),
        "exp": int((now - timedelta(hours=1)).timestamp()),
        "jti": str(uuid4()),
        "type": "access"
    }

    expired_token = jwt.encode(
        payload,
        settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm
    )

    response = client.post(
        "/auth/logout",
        headers={
            "Authorization": f"Bearer {expired_token}"
        }
    )

    assert response.status_code == 401

    assert response.json()["detail"] == (
        "Не вдалося підтвердити облікові дані"
    )

    assert response.headers["WWW-Authenticate"] == (
        "Bearer"
    )


def test_logout_api_inactive_user(client, db_session):
    """Неактивний користувач не може виконати logout."""

    from backend.app.models.user import User

    username = f"logout_inactive_{uuid4().hex[:12]}"

    register_response = client.post(
        "/auth/register",
        json={
            "name": "Inactive Logout User",
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "SecurePassword123!"
        }
    )

    assert login_response.status_code == 200

    access_token = login_response.json()["access_token"]

    user = db_session.query(User).filter(
        User.username == username
    ).one()

    user.is_active = False
    db_session.commit()

    response = client.post(
        "/auth/logout",
        headers={
            "Authorization": f"Bearer {access_token}"
        }
    )

    assert response.status_code == 401


def test_get_me_api_invalid_authorization_headers(client):
    """Reject requests with invalid Authorization headers."""

    invalid_headers = [
        {"Authorization": "Basic abc123"},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer "},
        {"Authorization": "InvalidScheme abc123"},
        {"Authorization": ""},
    ]

    for headers in invalid_headers:
        response = client.get(
            "/auth/me",
            headers=headers,
        )

        assert response.status_code == 401, (
            f"Unexpected status for {headers}: "
            f"{response.status_code}"
        )

        assert response.headers["WWW-Authenticate"] == "Bearer"
