import pytest
from pydantic import ValidationError

from backend.app.schemas.auth import (
    TokenResponse,
    UserLogin,
    UserResponse,
)
from backend.app.schemas.users import UserCreate


def valid_user_create_data():
    return {
        "name": "Тестовий користувач",
        "username": "test_user",
        "password": "StrongPass123",
    }


def test_valid_user_create():
    user = UserCreate(**valid_user_create_data())

    assert user.name == "Тестовий користувач"
    assert user.username == "test_user"
    assert user.role == "worker"


@pytest.mark.parametrize(
    "password",
    ["", "1234567"],
)
def test_short_password_rejected(password):
    data = valid_user_create_data()
    data["password"] = password

    with pytest.raises(ValidationError):
        UserCreate(**data)


@pytest.mark.parametrize(
    "username",
    ["ab", "user name", "user!", "тест"],
)
def test_invalid_username_rejected(username):
    data = valid_user_create_data()
    data["username"] = username

    with pytest.raises(ValidationError):
        UserCreate(**data)


@pytest.mark.parametrize(
    "name",
    ["", " ", "А"],
)
def test_invalid_name_rejected(name):
    data = valid_user_create_data()
    data["name"] = name

    with pytest.raises(ValidationError):
        UserCreate(**data)


def test_valid_login():
    login = UserLogin(
        username="test_user",
        password="StrongPass123",
    )

    assert login.username == "test_user"
    assert login.password == "StrongPass123"


def test_user_response_excludes_password():
    user = UserResponse(
        id=1,
        name="Тестовий користувач",
        username="test_user",
        role="worker",
        is_active=True,
    )

    result = user.model_dump()

    assert "password" not in result
    assert "password_hash" not in result
    assert result["role"] == "worker"


def test_invalid_role_rejected():
    with pytest.raises(ValidationError):
        UserResponse(
            id=1,
            name="Тестовий користувач",
            username="test_user",
            role="superadmin",
            is_active=True,
        )


def test_token_response():
    token = TokenResponse(access_token="test.jwt.token")

    assert token.access_token == "test.jwt.token"
    assert token.token_type == "bearer"
