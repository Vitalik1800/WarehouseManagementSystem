import pytest
from frontend.app.api.client import APIClientError, APIConnectionError, APIRequestError
from frontend.app.core.gui_errors import format_gui_error


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504])
def test_known_status_has_ukrainian_message(status):
    message = format_gui_error(APIRequestError(status, "SECRET INTERNAL DETAIL"))
    assert message
    assert "SECRET INTERNAL DETAIL" not in message


@pytest.mark.parametrize("status", [418, 501, 599])
def test_unknown_http_status_does_not_leak_backend_details(status):
    assert "secret" not in format_gui_error(APIRequestError(status, "secret")).lower()


def test_connection_error():
    assert "зв'язку" in format_gui_error(APIConnectionError("secret"))


def test_invalid_json_error():
    assert "secret" not in format_gui_error(APIClientError("secret"))


def test_validation_error():
    assert "Некоректні дані" in format_gui_error(ValueError("secret"))


def test_unknown_error_does_not_leak_details():
    assert "secret" not in format_gui_error(RuntimeError("secret"))
