from uuid import uuid4

import pytest

from backend.app.models.user import User

from fastapi.testclient import TestClient

from backend.app.db.session import get_db
from backend.app.main import app

from datetime import datetime, timedelta, timezone

import jwt

from backend.app.core.config import get_settings

from backend.app.core.security import create_access_token

from backend.app.core.security import decode_access_token
from backend.app.services.auth_service import AuthService
from tests.helpers.users import create_test_user


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


def test_public_registration_endpoint_not_found(client):
    """Public registration must remain unavailable."""
    response = client.post(
        "/auth/register",
        json={
            "name": "Unauthorized Registration",
            "username": "public_registration_test",
            "password": "SecurePassword123!"
        }
    )

    assert response.status_code == 404


def test_login_api_success(client, db_session):
    """Перевіряє успішний вхід та видачу JWT-токена."""
    username = f"api_login_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    user = create_test_user(
        db_session,
        name="Користувач для входу",
        username=username,
        password=password,
    )

    user_id = user.id

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


def test_login_api_invalid_password(client, db_session):
    """Перевіряє HTTP 401 для неправильного пароля."""
    username = f"api_login_wrong_{uuid4().hex[:12]}"

    create_test_user(
        db_session,
        name="Користувач для перевірки",
        username=username,
        password="CorrectPassword123!"
    )

    login_response = client.post(
        "/auth/login",
        json={
            "username": username,
            "password": "WrongPassword123!"
        }
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

    create_test_user(
        db_session,
        name="Неактивний користувач",
        username=username,
        password=password,
        is_active=False
    )

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


def test_get_me_api_success(client, db_session):
    """Перевіряє отримання поточного користувача за JWT."""
    username = f"api_me_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    user = create_test_user(
        db_session,
        name="Тестовий користувач",
        username=username,
        password=password,
    )

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
        "id": user.id,
        "name": user.name,
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

    user = create_test_user(
        db_session,
        name="Тестовий користувач",
        username=username,
        password=password,
    )

    user_id = user.id

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
    password = "SecurePassword123!"

    create_test_user(
        db_session,
        name="Тестовий користувач",
        username=username,
        password=password,
    )

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


def test_logout_api_success(client, db_session):
    """Перевіряє успішний вихід користувача через API."""

    username = f"logout_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    create_test_user(
        db_session,
        name="Тестовий користувач",
        username=username,
        password=password,
    )

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


def test_logout_api_invalid_token(client, db_session):
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


def test_logout_api_already_revoked_token(client, db_session):
    """Перевіряє повторний logout із відкликаним JWT."""

    username = f"logout_repeat_{uuid4().hex[:12]}"
    password = "SecurePassword123!"

    create_test_user(
        db_session,
        name="Тестовий користувач",
        username=username,
        password=password,
    )

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
    password = "SecurePassword123!"

    user = create_test_user(
        db_session,
        name="Тестовий користувач",
        username=username,
        password=password
    )

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
