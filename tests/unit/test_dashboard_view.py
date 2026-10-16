from concurrent.futures import Future
from unittest.mock import Mock

import customtkinter as ctk
import pytest

from frontend.app.api.client import (
    APIConnectionError,
    APIRequestError
)
from frontend.app.views.dashboard_view import DashboardView


SUMMARY = {
    "total_products": 12,
    "total_categories": 3,
    "total_suppliers": 4,
    "total_locations": 2,
    "in_stock_products": 9,
    "out_of_stock_products": 3
}


@pytest.fixture
def dashboard(monkeypatch):
    """Створює Dashboard без реальних HTTP-запитів."""

    root = ctk.CTk()
    root.withdraw()

    api_client = Mock()

    pending = Future()

    monkeypatch.setattr(
        "frontend.app.views.dashboard_view.ThreadPoolExecutor.submit",
        lambda self, *args, **kwargs: pending
    )

    view = DashboardView(
        root,
        api_client=api_client
    )
    view.pack()

    yield root, view, api_client, pending

    view.destroy()
    root.destroy()


def finish_request(view, future, *, result=None, error=None):
    """Завершує запит і обробляє результат у Tkinter."""

    if error is not None:
        future.set_exception(error)
    else:
        future.set_result(result)

    if view._poll_job is not None:
        view.after_cancel(view._poll_job)
        view._poll_job = None

    view._check_result()


def test_dashboard_creates_six_cards(dashboard):
    _, view, _, _ = dashboard

    assert len(view.value_labels) == 6
    assert set(view.value_labels) == set(SUMMARY)


def test_dashboard_starts_loading(dashboard):
    _, view, _, _ = dashboard

    assert view._future is not None
    assert view.refresh_button.cget("state") == "disabled"
    assert "Завантаження" in view.status_label.cget("text")


def test_dashboard_successful_response(dashboard):
    _, view, _, future = dashboard

    finish_request(
        view,
        future,
        result=SUMMARY.copy(),
    )

    for key, value in SUMMARY.items():
        assert view.value_labels[key].cget("text") == str(value)

    assert (
        view.status_label.cget("text")
        == "Статистику успішно оновлено"
    )
    assert view.refresh_button.cget("state") == "normal"


def test_dashboard_accepts_zero_values(dashboard):
    _, view, _, future = dashboard

    payload = {
        key: 0
        for key in SUMMARY
    }

    finish_request(
        view,
        future,
        result=payload
    )

    for label in view.value_labels.values():
        assert label.cget("text") == "0"


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"total_products": -1},
        {"total_products": "12"},
        {"total_products": True}
    ]
)
def test_dashboard_rejects_invalid_response(dashboard, payload):
    _, view, _, future = dashboard

    finish_request(
        view,
        future,
        result=payload
    )

    assert "Некоректні дані" in view.status_label.cget("text")
    assert view.refresh_button.cget("state") == "normal"


@pytest.mark.parametrize("status_code", [401, 403, 500])
def test_dashboard_handles_http_errors(dashboard, status_code):
    _, view, _, future = dashboard

    finish_request(
        view,
        future,
        error=APIRequestError(
            status_code,
            "HTTP request failed",
        )
    )

    assert str(status_code) in view.status_label.cget("text")
    assert view.refresh_button.cget("state") == "normal"


def test_dashboard_handles_connection_error(dashboard):
    _, view, _, future = dashboard

    finish_request(
        view,
        future,
        error=APIConnectionError("Backend unavailable")
    )

    assert "Помилка з'єднання" in view.status_label.cget("text")


def test_dashboard_prevents_duplicate_requests(dashboard):
    _, view, _, future = dashboard

    original_future = view._future

    view.refresh()
    view.refresh()

    assert view._future is original_future
    assert future.done() is False


def test_dashboard_closes_with_pending_request(dashboard):
    _, view, _, future = dashboard

    view.destroy()

    assert view._closed is True
    assert view._poll_job is None
    assert view._future is None
    assert future.cancelled() is True


def test_dashboard_does_not_update_destroyed_view(dashboard):
    _, view, _, _ = dashboard

    view.destroy()
    view._check_result()

    assert view._closed is True
