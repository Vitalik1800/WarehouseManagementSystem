from concurrent.futures import Future
from unittest.mock import Mock

import pytest

from frontend.app.api.client import (
    APIClientError,
    APIConnectionError,
    APIRequestError,
)
from frontend.app.views.register_view import RegisterView


def make_field(value: str):
    field = Mock()
    field.get_value.return_value = value.strip()
    field.entry.get.return_value = value
    field.validate.return_value = bool(value.strip())
    return field


def make_view(
    name="Test User",
    username="test_user",
    password="SecurePass123",
    confirmation="SecurePass123",
    role="worker",
):
    view = object.__new__(RegisterView)

    view._closed = False
    view._future = None
    view._poll_job = None

    view.name_field = make_field(name)
    view.username_field = make_field(username)
    view.password_field = make_field(password)
    view.confirm_password_field = make_field(confirmation)

    view.role_selector = Mock()
    view.role_selector.get.return_value = role

    view.notification = Mock()
    view.register_button = Mock()
    view.register_button.is_busy.return_value = False

    view.registration_service = Mock()
    view._executor = Mock()
    view.after = Mock(return_value="job-1")

    return view


def test_valid_fields():
    view = make_view()
    assert view._validate_fields() is True


@pytest.mark.parametrize(
    "field_name",
    ["name", "username", "password", "confirmation"],
)
def test_required_fields(field_name):
    values = {
        "name": "Test User",
        "username": "test_user",
        "password": "SecurePass123",
        "confirmation": "SecurePass123",
    }
    values[field_name] = ""

    view = make_view(**values)

    assert view._validate_fields() is False


@pytest.mark.parametrize(
    ("name", "username", "password", "confirmation"),
    [
        ("A", "test_user", "SecurePass123", "SecurePass123"),
        ("A" * 151, "test_user", "SecurePass123", "SecurePass123"),
        ("Test User", "ab", "SecurePass123", "SecurePass123"),
        ("Test User", "a" * 51, "SecurePass123", "SecurePass123"),
        ("Test User", "invalid-user", "SecurePass123", "SecurePass123"),
        ("Test User", "test_user", "short", "short"),
        ("Test User", "test_user", "a" * 129, "a" * 129),
        ("Test User", "test_user", "SecurePass123", "Different123"),
    ],
)
def test_invalid_field_values(name, username, password, confirmation):
    view = make_view(name, username, password, confirmation)
    assert view._validate_fields() is False


def test_register_submits_background_task():
    view = make_view()

    future = Future()
    view._executor.submit.return_value = future

    view.register()

    view.registration_service.register_user.assert_not_called()
    view._executor.submit.assert_called_once_with(
        view.registration_service.register_user,
        name="Test User",
        username="test_user",
        password="SecurePass123",
        role="worker",
    )
    view.register_button.set_busy.assert_called_once_with(True)
    view.after.assert_called_once_with(50, view._check_result)


def test_register_does_not_submit_invalid_fields():
    view = make_view(username="invalid-user")

    view.register()

    view._executor.submit.assert_not_called()


def test_register_ignores_busy_button():
    view = make_view()
    view.register_button.is_busy.return_value = True

    view.register()

    view._executor.submit.assert_not_called()


def test_register_ignores_closed_view():
    view = make_view()
    view._closed = True

    view.register()

    view._executor.submit.assert_not_called()


def test_register_handles_executor_shutdown():
    view = make_view()
    view._executor.submit.side_effect = RuntimeError("shutdown")

    view.register()

    view.register_button.set_busy.assert_any_call(False)
    view.notification.show.assert_called_once()


def completed_view(result=None, error=None):
    view = make_view()
    future = Future()

    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(result)

    view._future = future
    return view


def test_registration_success():
    view = completed_view(
        result={"id": 42, "username": "test_user"}
    )

    view._check_result()

    view.password_field.clear.assert_called_once()
    view.confirm_password_field.clear.assert_called_once()
    view.notification.show.assert_called_once_with(
        "Користувача test_user успішно створено.",
        variant="success",
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (APIConnectionError("offline"), "Немає з'єднання"),
        (APIRequestError(401, "unauthorized"), "Увійдіть повторно"),
        (APIRequestError(403, "forbidden"), "лише адміністратор"),
        (APIRequestError(409, "conflict"), "уже існує"),
        (APIRequestError(422, "invalid"), "відхилив"),
        (APIRequestError(500, "error"), "HTTP 500"),
        (APIClientError("invalid"), "Не вдалося"),
        (ValueError("invalid"), "Не вдалося"),
        (RuntimeError("unexpected"), "непередбачена"),
    ],
)
def test_registration_errors(error, expected):
    view = completed_view(error=error)

    view._check_result()

    args, kwargs = view.notification.show.call_args
    assert expected in args[0]
    assert kwargs["variant"] == "error"


def test_pending_future_is_polled_again():
    view = make_view()
    view._future = Future()

    view._check_result()

    view.after.assert_called_once_with(50, view._check_result)
    assert view._poll_job == "job-1"


def test_closed_view_ignores_result():
    view = completed_view(result={"id": 42, "username": "test_user"})
    view._closed = True

    view._check_result()

    view.notification.show.assert_not_called()
