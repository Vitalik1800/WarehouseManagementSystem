from unittest.mock import Mock

import pytest

from frontend.app.api.client import APIRequestError
from frontend.app.services.user_registration_service import (
    UserRegistrationError,
    UserRegistrationService,
)


@pytest.fixture
def api_client():
    client = Mock()
    client.is_authenticated = True
    client.post.return_value = {
        "id": 42,
        "name": "Test User",
        "username": "test_user",
        "role": "worker",
        "is_active": True,
    }
    return client


@pytest.fixture
def service(api_client):
    return UserRegistrationService(api_client)


def test_register_user_success(service, api_client):
    result = service.register_user(
        name=" Test User ",
        username=" test_user ",
        password="SecurePass123",
    )

    assert result["id"] == 42

    api_client.post.assert_called_once_with(
        "/users",
        json={
            "name": "Test User",
            "username": "test_user",
            "password": "SecurePass123",
            "role": "worker",
        },
    )


def test_register_admin(service, api_client):
    service.register_user(
        name="Administrator",
        username="new_admin",
        password="SecurePass123",
        role="admin",
    )

    assert api_client.post.call_args.kwargs["json"]["role"] == "admin"


@pytest.mark.parametrize(
    ("name", "username", "password", "role"),
    [
        (" ", "valid_user", "SecurePass123", "worker"),
        ("A", "valid_user", "SecurePass123", "worker"),
        ("A" * 151, "valid_user", "SecurePass123", "worker"),
        ("Test User", "ab", "SecurePass123", "worker"),
        ("Test User", "a" * 51, "SecurePass123", "worker"),
        ("Test User", "invalid-user", "SecurePass123", "worker"),
        ("Test User", "користувач", "SecurePass123", "worker"),
        ("Test User", "valid_user", "short", "worker"),
        ("Test User", "valid_user", "a" * 129, "worker"),
        ("Test User", "valid_user", "SecurePass123", "manager"),
    ],
)
def test_invalid_fields_do_not_send_request(
    service, api_client, name, username, password, role
):
    with pytest.raises(ValueError):
        service.register_user(
            name=name,
            username=username,
            password=password,
            role=role,
        )

    api_client.post.assert_not_called()


def test_registration_requires_authentication(service, api_client):
    api_client.is_authenticated = False

    with pytest.raises(UserRegistrationError):
        service.register_user(
            name="Test User",
            username="test_user",
            password="SecurePass123",
        )

    api_client.post.assert_not_called()


@pytest.mark.parametrize("status_code", [401, 403, 409, 422])
def test_http_errors_are_propagated(service, api_client, status_code):
    api_client.post.side_effect = APIRequestError(
        status_code=status_code,
        message="Request failed",
    )

    with pytest.raises(APIRequestError) as exc_info:
        service.register_user(
            name="Test User",
            username="test_user",
            password="SecurePass123",
        )

    assert exc_info.value.status_code == status_code


@pytest.mark.parametrize(
    "response",
    [
        None,
        [],
        "invalid",
        {},
        {"id": None},
        {"id": "42"},
        {"id": True},
    ],
)
def test_invalid_backend_response(service, api_client, response):
    api_client.post.return_value = response

    with pytest.raises(UserRegistrationError):
        service.register_user(
            name="Test User",
            username="test_user",
            password="SecurePass123",
        )
