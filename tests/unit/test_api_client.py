import httpx
import pytest

from frontend.app.api.client import (
    APIClient,
    APIClientError,
    APIConnectionError,
    APIRequestError
)


def make_client(handler):
    return APIClient(
        transport=httpx.MockTransport(handler)
    )


def test_get_success():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/health"
        return httpx.Response(
            200,
            json={"status": "ok"},
        )

    with make_client(handler) as client:
        assert client.get("/health") == {"status": "ok"}


def test_post_json():
    def handler(request):
        assert request.method == "POST"
        assert request.url.path == "/auth/login"
        assert b"username" in request.content
        return httpx.Response(
            200,
            json={"access_token": "test-token"},
        )

    with make_client(handler) as client:
        result = client.post(
            "/auth/login",
            json={
                "username": "admin",
                "password": "test-password",
            },
        )

    assert result["access_token"] == "test-token"


def test_no_content():
    with make_client(
        lambda request: httpx.Response(204)
    ) as client:
        assert client.post("/auth/logout") is None


def test_bearer_token():
    def handler(request):
        assert (
            request.headers["Authorization"]
            == "Bearer test-token"
        )
        return httpx.Response(200, json={"id": 1})

    with make_client(handler) as client:
        client.set_access_token("test-token")
        assert client.is_authenticated
        assert client.get("/auth/me") == {"id": 1}

        client.clear_access_token()
        assert not client.is_authenticated


@pytest.mark.parametrize(
    "status",
    [401, 422, 500],
)
def test_http_errors(status):
    with make_client(
        lambda request: httpx.Response(
            status,
            json={"detail": "Test error"},
        )
    ) as client:
        with pytest.raises(APIRequestError) as exc:
            client.get("/test")

    assert exc.value.status_code == status
    assert exc.value.message == "Test error"


def test_connection_error():
    def handler(request):
        raise httpx.ConnectError(
            "Connection refused",
            request=request,
        )

    with make_client(handler) as client:
        with pytest.raises(APIConnectionError):
            client.get("/health")


def test_invalid_json():
    with make_client(
        lambda request: httpx.Response(
            200,
            text="not-json",
        )
    ) as client:
        with pytest.raises(APIClientError):
            client.get("/health")


def test_invalid_endpoint():
    with make_client(
        lambda request: httpx.Response(200)
    ) as client:
        with pytest.raises(ValueError):
            client.get("health")


def test_empty_token():
    with make_client(
        lambda request: httpx.Response(200)
    ) as client:
        with pytest.raises(ValueError):
            client.set_access_token("  ")



def test_put_success():
    def handler(request):
        assert request.method == "PUT"
        assert request.url.path == "/products/1"
        return httpx.Response(200, json={"updated": True})

    with make_client(handler) as client:
        result = client.put(
            "/products/1",
            json={"name": "Updated product"},
        )

    assert result == {"updated": True}


def test_patch_success():
    def handler(request):
        assert request.method == "PATCH"
        return httpx.Response(200, json={"patched": True})

    with make_client(handler) as client:
        result = client.patch(
            "/products/1",
            json={"name": "New name"},
        )

    assert result == {"patched": True}


def test_delete_success():
    def handler(request):
        assert request.method == "DELETE"
        return httpx.Response(204)

    with make_client(handler) as client:
        assert client.delete("/products/1") is None


def test_query_parameters():
    def handler(request):
        assert request.url.params["page"] == "2"
        assert request.url.params["limit"] == "10"
        return httpx.Response(200, json={"items": []})

    with make_client(handler) as client:
        result = client.get(
            "/products",
            params={"page": 2, "limit": 10},
        )

    assert result == {"items": []}


def test_custom_headers():
    def handler(request):
        assert request.headers["X-Test"] == "warehouse"
        return httpx.Response(200, json={"ok": True})

    with make_client(handler) as client:
        result = client.get(
            "/health",
            headers={"X-Test": "warehouse"},
        )

    assert result == {"ok": True}


def test_authorization_header():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer abc"
        return httpx.Response(200, json={"ok": True})

    with make_client(handler) as client:
        client.set_access_token("abc")
        assert client.get("/auth/me") == {"ok": True}


def test_clear_token_removes_header():
    def handler(request):
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"ok": True})

    with make_client(handler) as client:
        client.set_access_token("abc")
        client.clear_access_token()
        assert client.get("/health") == {"ok": True}


def test_timeout_error():
    def handler(request):
        raise httpx.ReadTimeout(
            "Request timed out",
            request=request,
        )

    with make_client(handler) as client:
        with pytest.raises(APIConnectionError):
            client.get("/health")


def test_server_error_plain_text():
    with make_client(
        lambda request: httpx.Response(
            500,
            text="Internal Server Error",
        )
    ) as client:
        with pytest.raises(APIRequestError) as exc:
            client.get("/health")

    assert exc.value.status_code == 500
    assert exc.value.message == "Internal Server Error"


def test_empty_response():
    with make_client(
        lambda request: httpx.Response(200, content=b"")
    ) as client:
        assert client.get("/health") is None


def test_context_manager_closes_client():
    client = make_client(
        lambda request: httpx.Response(200)
    )

    with client:
        assert not client._client.is_closed

    assert client._client.is_closed


def test_reject_auth_kwarg():
    with make_client(
        lambda request: httpx.Response(200)
    ) as client:
        with pytest.raises(ValueError):
            client.get("/health", auth=("user", "password"))
