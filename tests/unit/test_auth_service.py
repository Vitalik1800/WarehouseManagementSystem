from unittest.mock import patch

import pytest
from unittest.mock import Mock

from backend.app.core.security import hash_password
from backend.app.services.auth_service import (
    AuthService,
    InvalidCredentialsError
)


def test_authenticate_success():
    """Перевіряє успішну автентифікацію користувача."""
    password = "SecurePassword123!"

    user = Mock()
    user.id = 1
    user.username = "test_worker"
    user.password_hash = hash_password(password)
    user.is_active = True

    db = Mock()
    service = AuthService(db)
    service.users.get_by_username = Mock(return_value=user)

    authenticated_user = service.authenticate(
        username="test_worker",
        password=password,
    )

    assert authenticated_user is user

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )



def test_authenticate_invalid_password():
    """Відхиляє автентифікацію з неправильним паролем."""
    user = Mock()
    user.id = 1
    user.username = "test_worker"
    user.password_hash = hash_password("CorrectPassword123!")
    user.is_active = True

    db = Mock()
    service = AuthService(db)
    service.users.get_by_username = Mock(return_value=user)

    with pytest.raises(
        InvalidCredentialsError,
        match="Неправильний логін або пароль"
    ):
        service.authenticate(
            username="test_worker",
            password="WrongPassword123!"
        )

    service.users.get_by_username.assert_called_once_with(
        "test_worker"
    )



def test_authenticate_nonexistent_user():
    """Відхиляє автентифікацію неіснуючого користувача."""
    db = Mock()

    service = AuthService(db)
    service.users.get_by_username = Mock(return_value=None)

    with pytest.raises(
        InvalidCredentialsError,
        match="Неправильний логін або пароль"
    ):
        service.authenticate(
            username="nonexistent_user",
            password="SomePassword123!"
        )

    service.users.get_by_username.assert_called_once_with(
        "nonexistent_user"
    )



def test_authenticate_inactive_user():
    """Відхиляє автентифікацію неактивного користувача."""
    password = "SecurePassword123!"

    user = Mock()
    user.id = 1
    user.username = "inactive_worker"
    user.password_hash = hash_password(password)
    user.is_active = False

    db = Mock()
    service = AuthService(db)
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



def test_authenticate_nonexistent_user_verifies_dummy_password():
    """Перевіряє використання фіктивного хешу для невідомого логіна."""
    db = Mock()
    service = AuthService(db)

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
