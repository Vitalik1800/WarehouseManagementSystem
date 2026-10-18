
from unittest.mock import Mock, patch

from frontend.app.services.credential_store import CredentialStore

import httpx
import pytest

from backend.app.core.security import hash_password
from backend.app.services.auth_service import (
    AuthService as BackendAuthService,
    InvalidCredentialsError
)
from frontend.app.services.auth_service import (
    AuthService as FrontendAuthService,
    AuthenticationError
)
from frontend.app.api.client import (
    APIClient,
    APIConnectionError,
    APIRequestError
)


# ============================================================
# BACKEND AUTH SERVICE
# ============================================================


def test_backend_authenticate_success():
    """Перевіряє успішну автентифікацію користувача."""
    password = "SecurePassword123!"

    user = Mock()
    user.id = 1
    user.username = "test_worker"
    user.password_hash = hash_password(password)
    user.is_active = True

    db = Mock()
    service = BackendAuthService(db)
    service.users.get_by_username = Mock(return_value=user)

    authenticated_user = service.authenticate(
        username="test_worker",
        password=password,
    )

    assert authenticated_user is user

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )


def test_backend_authenticate_invalid_password():
    """Відхиляє неправильний пароль."""
    user = Mock()
    user.id = 1
    user.username = "test_worker"
    user.password_hash = hash_password("CorrectPassword123!")
    user.is_active = True

    db = Mock()
    service = BackendAuthService(db)
    service.users.get_by_username = Mock(return_value=user)

    with pytest.raises(
        InvalidCredentialsError,
        match="Неправильний логін або пароль",
    ):
        service.authenticate(
            username="test_worker",
            password="WrongPassword123!",
        )

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )


def test_backend_authenticate_nonexistent_user():
    """Відхиляє неіснуючого користувача."""
    db = Mock()
    service = BackendAuthService(db)
    service.users.get_by_username = Mock(return_value=None)

    with pytest.raises(
        InvalidCredentialsError,
        match="Неправильний логін або пароль",
    ):
        service.authenticate(
            username="nonexistent_user",
            password="SomePassword123!",
        )

    service.users.get_by_username.assert_called_once_with(
        "nonexistent_user"
    )


def test_backend_authenticate_inactive_user():
    """Відхиляє неактивного користувача."""
    password = "SecurePassword123!"

    user = Mock()
    user.id = 1
    user.username = "inactive_worker"
    user.password_hash = hash_password(password)
    user.is_active = False

    db = Mock()
    service = BackendAuthService(db)
    service.users.get_by_username = Mock(return_value=user)

    with pytest.raises(
        InvalidCredentialsError,
        match="Неправильний логін або пароль",
    ):
        service.authenticate(
            username="inactive_worker",
            password=password,
        )

    service.users.get_by_username.assert_called_once_with(
        "inactive_worker"
    )


def test_backend_authenticate_nonexistent_user_verifies_dummy_password():
    """Перевіряє використання фіктивного Argon2-хешу."""
    db = Mock()
    service = BackendAuthService(db)

    service.users.get_by_username = Mock(return_value=None)

    with patch(
        "backend.app.services.auth_service.verify_password",
        return_value=False,
    ) as mocked_verify:
        with pytest.raises(
            InvalidCredentialsError,
            match="Неправильний логін або пароль",
        ):
            service.authenticate(
                username="unknown_user",
                password="SomePassword123!",
            )

    service.users.get_by_username.assert_called_once_with(
        "unknown_user"
    )

    mocked_verify.assert_called_once()

    args, kwargs = mocked_verify.call_args

    assert args[0] == "SomePassword123!"
    assert args[1].startswith("$argon2id$")
    assert kwargs == {}


# ============================================================
# FRONTEND AUTH SERVICE
# ============================================================


@pytest.fixture(autouse=True)
def isolated_windows_credentials(monkeypatch):
    """Never read or write the actual Windows Credential Manager in these tests."""
    secrets = {}
    fake = Mock(spec=CredentialStore)
    fake.load.side_effect = lambda: secrets.get("refresh")
    fake.save.side_effect = lambda token: secrets.__setitem__("refresh", token)
    fake.delete.side_effect = lambda: secrets.pop("refresh", None)
    monkeypatch.setattr("frontend.app.services.auth_service.CredentialStore", lambda: fake)



@pytest.fixture
def auth_client():
    """Створює HTTP-клієнт із тестовим Backend."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(
                200,
                json={
                    "access_token": "test-jwt-token",
                    "refresh_token": "test-refresh-token",
                    "token_type": "bearer",
                },
            )

        if request.url.path == "/auth/me":
            if (
                request.headers.get("Authorization")
                != "Bearer test-jwt-token"
            ):
                return httpx.Response(
                    401,
                    json={"detail": "Unauthorized"},
                )

            return httpx.Response(
                200,
                json={
                    "id": 1,
                    "name": "Test User",
                    "username": "tester",
                    "role": "worker",
                    "is_active": True,
                },
            )

        if request.url.path == "/auth/logout":
            return httpx.Response(204)

        return httpx.Response(404)

    client = APIClient(
        transport=httpx.MockTransport(handler)
    )

    yield client

    client.close()


@pytest.fixture
def frontend_auth_service(auth_client):
    """Створює Frontend AuthService."""
    return FrontendAuthService(auth_client)


def test_frontend_login_success(frontend_auth_service):
    response = frontend_auth_service.login(
        "tester",
        "password123",
    )

    assert response["access_token"] == "test-jwt-token"
    assert frontend_auth_service.is_authenticated is True


def test_frontend_login_strips_username():
    def handler(request: httpx.Request) -> httpx.Response:
        import json

        payload = json.loads(request.content)

        assert payload["username"] == "tester"
        assert payload["password"] == "password123"

        return httpx.Response(
            200,
            json={
                "access_token": "token",
                "refresh_token": "test-refresh-token",
                "token_type": "bearer",
            },
        )

    with APIClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        service = FrontendAuthService(client)
        service.login(" tester ", "password123")

        assert service.is_authenticated is True


@pytest.mark.parametrize(
    "username,password",
    [
        ("", "password123"),
        ("   ", "password123"),
        ("tester", ""),
    ],
)
def test_frontend_login_invalid_input(
    frontend_auth_service,
    username,
    password,
):
    with pytest.raises(ValueError):
        frontend_auth_service.login(username, password)


def test_frontend_login_invalid_response():
    with APIClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"unexpected": "value"},
            )
        )
    ) as client:
        service = FrontendAuthService(client)

        with pytest.raises(AuthenticationError):
            service.login("tester", "password123")

        assert service.is_authenticated is False


def test_frontend_login_invalid_token_type():
    with APIClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "access_token": "token",
                    "token_type": "basic",
                },
            )
        )
    ) as client:
        service = FrontendAuthService(client)

        with pytest.raises(AuthenticationError):
            service.login("tester", "password123")

        assert service.is_authenticated is False


def test_frontend_login_clears_previous_token(
    frontend_auth_service,
):
    frontend_auth_service.api_client.set_access_token(
        "old-token"
    )

    frontend_auth_service.login(
        "tester",
        "password123",
    )

    assert frontend_auth_service.is_authenticated is True


def test_frontend_get_current_user_success(
    frontend_auth_service,
):
    frontend_auth_service.login(
        "tester",
        "password123",
    )

    user = frontend_auth_service.get_current_user()

    assert user["id"] == 1
    assert user["username"] == "tester"
    assert user["role"] == "worker"


def test_frontend_get_current_user_without_login(
    frontend_auth_service,
):
    with pytest.raises(AuthenticationError):
        frontend_auth_service.get_current_user()


def test_frontend_get_current_user_invalid_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=["invalid"],
        )

    with APIClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        client.set_access_token("token")
        service = FrontendAuthService(client)

        with pytest.raises(AuthenticationError):
            service.get_current_user()


def test_frontend_get_current_user_unauthorized():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"detail": "Unauthorized"},
        )

    with APIClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        client.set_access_token("invalid-token")
        service = FrontendAuthService(client)

        with pytest.raises(APIRequestError) as exc_info:
            service.get_current_user()

        assert exc_info.value.status_code == 401
        assert service.is_authenticated is False


def test_frontend_logout_success(frontend_auth_service):
    frontend_auth_service.login(
        "tester",
        "password123",
    )

    frontend_auth_service.logout()

    assert frontend_auth_service.is_authenticated is False


def test_frontend_logout_without_login(
    frontend_auth_service,
):
    frontend_auth_service.logout()

    assert frontend_auth_service.is_authenticated is False


def test_frontend_logout_unauthorized():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={"detail": "Token revoked"},
        )

    with APIClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        client.set_access_token("expired-token")
        service = FrontendAuthService(client)

        service.logout()

        assert service.is_authenticated is False


def test_frontend_logout_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(
            "Backend unavailable",
            request=request,
        )

    with APIClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        client.set_access_token("token")
        service = FrontendAuthService(client)

        with pytest.raises(APIConnectionError):
            service.logout()

        assert service.is_authenticated is False


def test_frontend_logout_server_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            500,
            json={"detail": "Internal Server Error"},
        )

    with APIClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        client.set_access_token("token")
        service = FrontendAuthService(client)

        with pytest.raises(APIRequestError):
            service.logout()

        assert service.is_authenticated is False


def test_frontend_login_non_dict_response():
    """Відхиляє відповідь авторизації, яка не є JSON-об'єктом."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=["invalid", "login", "response"],
        )

    with APIClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        service = FrontendAuthService(client)

        with pytest.raises(
            AuthenticationError,
            match="invalid authentication data",
        ):
            service.login(
                username="tester",
                password="password123",
            )

        assert service.is_authenticated is False
