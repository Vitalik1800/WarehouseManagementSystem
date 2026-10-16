from typing import Any

import httpx

from frontend.app.core.config import (
    FrontendSettings,
    get_frontend_settings,
)


class APIClientError(Exception):
    """Базова помилка API-клієнта."""


class APIConnectionError(APIClientError):
    """Не вдалося встановити з'єднання з Backend."""


class APIRequestError(APIClientError):
    """Backend повернув помилку HTTP."""

    def __init__(
        self,
        status_code: int,
        message: str,
    ) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class APIClient:
    """HTTP-клієнт для взаємодії Frontend із FastAPI."""

    def __init__(
        self,
        settings: FrontendSettings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_frontend_settings()
        self._access_token: str | None = None

        self._client = httpx.Client(
            base_url=self.settings.frontend_api_base_url,
            timeout=self.settings.frontend_request_timeout,
            transport=transport,
            headers={"Accept": "application/json"},
        )

    def set_access_token(self, token: str) -> None:
        if not token or not token.strip():
            raise ValueError("Access token cannot be empty")

        self._access_token = token.strip()

    def clear_access_token(self) -> None:
        self._access_token = None

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    def request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> Any:
        if not endpoint.startswith("/") or endpoint.startswith("//"):
            raise ValueError(
                "API endpoint must start with a single '/'"
            )

        if "auth" in kwargs:
            raise ValueError(
                "Use set_access_token() for authentication"
            )

        headers = dict(kwargs.pop("headers", {}) or {})

        if self._access_token:
            headers["Authorization"] = (
                f"Bearer {self._access_token}"
            )

        try:
            response = self._client.request(
                method=method,
                url=endpoint.lstrip("/"),
                headers=headers,
                **kwargs,
            )

            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            response = exc.response
            message = response.text

            try:
                payload = response.json()
                if isinstance(payload, dict):
                    detail = payload.get("detail", message)
                    message = (
                        detail
                        if isinstance(detail, str)
                        else str(detail)
                    )
            except ValueError:
                pass

            raise APIRequestError(
                status_code=response.status_code,
                message=message,
            ) from exc

        except httpx.RequestError as exc:
            raise APIConnectionError(
                "Unable to communicate with Backend"
            ) from exc

        if response.status_code == 204 or not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise APIClientError(
                "Backend returned an invalid JSON response"
            ) from exc

    def get(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("POST", endpoint, **kwargs)

    def put(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("PUT", endpoint, **kwargs)

    def patch(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("PATCH", endpoint, **kwargs)

    def delete(self, endpoint: str, **kwargs: Any) -> Any:
        return self.request("DELETE", endpoint, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()
