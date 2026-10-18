from concurrent.futures import Future
from unittest.mock import Mock

import customtkinter as ctk
import pytest

from tests.gui_cleanup import cleanup_gui

from frontend.app.api.client import (
    APIConnectionError,
    APIRequestError
)
from frontend.app.views.login_view import LoginView

from frontend.app.services.auth_service import AuthenticationError
from frontend.app.api.client import APIClientError


@pytest.fixture
def login_gui():
    """Створює ізольовану форму авторизації."""

    root = ctk.CTk()
    root.withdraw()

    auth_service = Mock()
    on_success = Mock()

    view = LoginView(
        root,
        auth_service=auth_service,
        on_login_success=on_success
    )
    view.pack()

    root.update_idletasks()

    yield view, auth_service, on_success

    if view.winfo_exists():
        view.destroy()

    cleanup_gui(root)


def fill_form(
    view: LoginView,
    username: str = "tester",
    password: str = "password123"
):
    view.username_field.set_value(username)
    view.password_field.set_value(password)


def complete_future(
    view: LoginView,
    *,
    result=None,
    error=None
):
    """Підставляє завершене фонове завдання."""

    if view._poll_job is not None:
        view.after_cancel(view._poll_job)
        view._poll_job = None

    future = Future()

    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(result)

    view._future = future
    view.login_button.set_busy(True)

    view._check_login_result()


def test_login_view_initial_state(login_gui):
    view, _, on_success = login_gui

    assert view.username_field.get_value() == ""
    assert view.password_field.get_value() == ""
    assert view.login_button.is_busy() is False
    assert view._future is None
    on_success.assert_not_called()


@pytest.mark.parametrize(
    "username,password",
    [
        ("", "password123"),
        ("   ", "password123"),
        ("tester", "")
    ]
)
def test_login_view_rejects_empty_fields(
    login_gui,
    username,
    password
):
    view, auth_service, on_success = login_gui

    fill_form(view, username, password)
    view.login()

    assert view.login_button.is_busy() is False
    assert view._future is None
    auth_service.login.assert_not_called()
    on_success.assert_not_called()


def test_login_view_starts_background_authentication(login_gui):
    view, _, _ = login_gui

    fill_form(view)
    view.login()

    assert view.login_button.is_busy() is True
    assert view._future is not None


def test_login_view_prevents_duplicate_requests(login_gui):
    view, _, _ = login_gui

    fill_form(view)
    view.login()

    first_future = view._future

    view.login()

    assert view._future is first_future


def test_login_view_preserves_password_spaces(login_gui):
    view, auth_service, _ = login_gui

    fill_form(
        view,
        username=" tester ",
        password=" password123 "
    )

    # Викликаємо робочу функцію без Tkinter-потоку.
    auth_service.get_current_user.return_value = {
        "id": 1,
        "username": "tester",
        "role": "admin"
    }

    view._authenticate(
        view.username_field.get_value(),
        view.password_field.entry.get()
    )

    auth_service.login.assert_called_once_with(
        username="tester",
        password=" password123 "
    )


def test_login_view_success(login_gui):
    view, _, on_success = login_gui

    fill_form(view)

    user = {
        "id": 1,
        "username": "tester",
        "role": "admin"
    }

    complete_future(view, result=user)

    on_success.assert_called_once_with(user)
    assert view.password_field.entry.get() == ""
    assert view.login_button.is_busy() is False


def test_login_view_connection_error(login_gui):
    view, _, on_success = login_gui

    complete_future(
        view,
        error=APIConnectionError("Connection failed"),
    )

    assert "з'єднання" in view.notification.get_message()
    assert view.login_button.is_busy() is False
    on_success.assert_not_called()


@pytest.mark.parametrize(
    "status_code,expected_message",
    [
        (401, "Неправильний логін"),
        (403, "Доступ"),
        (500, "HTTP 500")
    ]
)
def test_login_view_http_errors(
    login_gui,
    status_code,
    expected_message
):
    """Перевіряє реальну обробку HTTP-помилок."""

    view, _, on_success = login_gui

    complete_future(
        view,
        error=APIRequestError(
            status_code=status_code,
            message=f"HTTP {status_code}"
        )
    )

    assert expected_message in view.notification.get_message()
    assert view.login_button.is_busy() is False
    assert view._future is None

    on_success.assert_not_called()


def test_login_view_enter_triggers_login(login_gui):
    view, _, _ = login_gui

    fill_form(view)
    view._on_enter()

    assert view._future is not None


def test_login_view_destroy_marks_closed(login_gui):
    view, _, _ = login_gui

    view.destroy()

    assert view._closed is True
    assert view._poll_job is None


@pytest.mark.parametrize(
    "error",
    [
        AuthenticationError("Invalid authentication data"),
        APIClientError("Unexpected API error"),
        ValueError("Invalid input")
    ]
)
def test_login_view_authentication_errors(
    login_gui,
    error
):
    """Перевіряє обробку помилок авторизації."""

    view, _, on_success = login_gui

    complete_future(
        view,
        error=error
    )

    assert (
        "Не вдалося виконати авторизацію"
        in view.notification.get_message()
    )
    assert view.login_button.is_busy() is False

    on_success.assert_not_called()


def test_login_view_pending_future(login_gui):
    """Форма очікує завершення фонового завдання."""

    view, _, on_success = login_gui

    future = Future()

    view._future = future
    view.login_button.set_busy(True)

    view._check_login_result()

    assert view._future is future
    assert view.login_button.is_busy() is True
    assert view._poll_job is not None

    on_success.assert_not_called()


def test_login_view_without_future(login_gui):
    """Відсутність фонового завдання не викликає помилок."""

    view, _, on_success = login_gui

    view._future = None
    view._check_login_result()

    assert view._future is None
    on_success.assert_not_called()


def test_login_view_closed_ignores_result(login_gui):
    """Закрита форма не обробляє результат авторизації."""

    view, _, on_success = login_gui

    future = Future()
    future.set_result({"username": "tester"})

    view._future = future
    view._closed = True

    view._check_login_result()

    on_success.assert_not_called()


def test_login_view_executor_submit_failure(
    login_gui,
    monkeypatch
):
    """Перевіряє помилку запуску фонового завдання."""

    view, auth_service, on_success = login_gui

    fill_form(view)

    def fail_submit(*args, **kwargs):
        raise RuntimeError("Executor is unavailable")

    monkeypatch.setattr(
        view._executor,
        "submit",
        fail_submit
    )

    view.login()

    assert view.login_button.is_busy() is False
    assert (
        "Не вдалося запустити авторизацію"
        in view.notification.get_message()
    )

    auth_service.login.assert_not_called()
    on_success.assert_not_called()


def test_login_view_destroy_handles_cancel_error(
    login_gui,
    monkeypatch,
):
    """Перевіряє безпечне закриття при помилці after_cancel."""

    view, _, _ = login_gui

    view._poll_job = "invalid-job"

    def fail_cancel(_job):
        raise ValueError("Invalid scheduled callback")

    monkeypatch.setattr(
        view,
        "after_cancel",
        fail_cancel
    )

    view.destroy()

    assert view._closed is True
    assert view._poll_job is None
