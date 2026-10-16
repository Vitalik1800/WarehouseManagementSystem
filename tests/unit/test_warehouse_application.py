
from concurrent.futures import Future
from unittest.mock import Mock

import pytest

from frontend.app.api.client import APIConnectionError
from frontend.main import WarehouseApplication


TEST_USER = {
    "id": 1,
    "username": "tester",
    "role": "admin"
}


@pytest.fixture
def app(monkeypatch):
    """Створює ізольований застосунок без реальних HTTP-запитів."""

    monkeypatch.setattr(
        "frontend.main.APIClient",
        Mock
    )

    application = WarehouseApplication()
    application.withdraw()
    application.update_idletasks()

    yield application

    if not application._closing:
        application.on_close()


def authenticate(app):
    """Simulates successful authentication."""

    app.auth_service.api_client.is_authenticated = True
    app._on_login_success(TEST_USER.copy())


def set_logout_future(app, *, error=None):
    """Replaces the background logout result with a completed future."""

    if app._logout_poll_job is not None:
        app.after_cancel(app._logout_poll_job)
        app._logout_poll_job = None

    future = Future()

    if error is None:
        future.set_result(None)
    else:
        future.set_exception(error)

    app._logout_future = future

    return future


def test_application_starts_with_login(app):
    assert app.login_view is not None
    assert app.main_layout is None
    assert app.current_user is None


def test_application_uses_shared_auth_service(app):
    assert app.login_view.auth_service is app.auth_service
    assert app.auth_service.api_client is app.api_client


def test_application_login_success(app):
    authenticate(app)

    assert app.login_view is None
    assert app.main_layout is not None
    assert app.current_user == TEST_USER


def test_application_rejects_login_without_token(app):
    app.auth_service.api_client.is_authenticated = False

    app._on_login_success(TEST_USER)

    assert app.login_view is not None
    assert app.main_layout is None
    assert app.current_user is None


def test_application_rejects_invalid_user(app):
    app.auth_service.api_client.is_authenticated = True

    app._on_login_success(None)

    assert app.login_view is not None
    assert app.main_layout is None
    assert app.current_user is None


def test_main_layout_has_logout_button(app):
    authenticate(app)

    assert app.main_layout.logout_button is not None
    assert app.main_layout.logout_button.cget("text") == "Вийти"


def test_application_logout_returns_to_login(app, monkeypatch):
    authenticate(app)

    monkeypatch.setattr(
        app._executor,
        "submit",
        lambda *args, **kwargs: Future()
    )

    app._on_logout()

    assert app._logging_out is True
    assert app._logout_future is not None

    set_logout_future(app)
    app._check_logout_result()

    assert app._logging_out is False
    assert app.main_layout is None
    assert app.login_view is not None
    assert app.current_user is None

    app.api_client.clear_access_token.assert_called()


def test_application_prevents_duplicate_logout(app, monkeypatch):
    authenticate(app)

    submit = Mock(return_value=Future())

    monkeypatch.setattr(
        app._executor,
        "submit",
        submit
    )

    app._on_logout()
    app._on_logout()

    submit.assert_called_once()


def test_application_logout_connection_error(app, monkeypatch):
    authenticate(app)

    monkeypatch.setattr(
        app._executor,
        "submit",
        lambda *args, **kwargs: Future()
    )

    app._on_logout()

    set_logout_future(
        app,
        error=APIConnectionError("Backend unavailable")
    )

    app._check_logout_result()

    assert app.login_view is not None
    assert app.main_layout is None
    assert app.current_user is None
    assert app._logging_out is False


def test_application_logout_pending_future(app, monkeypatch):
    authenticate(app)

    pending = Future()

    monkeypatch.setattr(
        app._executor,
        "submit",
        lambda *args, **kwargs: pending
    )

    app._on_logout()

    app._check_logout_result()

    assert app._logging_out is True
    assert app.main_layout is not None
    assert app._logout_poll_job is not None


def test_application_close_cleans_resources(app):
    api_client = app.api_client

    app.on_close()

    assert app._closing is True
    assert app.current_user is None
    assert app.login_view is None
    assert app.main_layout is None

    api_client.clear_access_token.assert_called()
    api_client.close.assert_called_once()


def test_application_close_during_logout(app, monkeypatch):
    authenticate(app)

    pending = Future()

    monkeypatch.setattr(
        app._executor,
        "submit",
        lambda *args, **kwargs: pending
    )

    app._on_logout()
    app.on_close()

    assert app._closing is True
    assert app._logout_poll_job is None
    assert app.main_layout is None


def test_application_relogin_after_logout(app):
    authenticate(app)

    app._complete_logout()

    assert app.login_view is not None

    authenticate(app)

    assert app.main_layout is not None
    assert app.current_user == TEST_USER
