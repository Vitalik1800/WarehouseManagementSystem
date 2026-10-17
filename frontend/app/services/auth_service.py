from typing import Any

from frontend.app.api.client import (
    APIClient,
    APIClientError,
    APIRequestError
)


class AuthenticationError(APIClientError):
    """Помилка обробки даних авторизації."""


class AuthService:
    """Сервіс авторизації настільного застосунку."""

    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    def login(
        self,
        username: str,
        password: str
    ) -> dict[str, Any]:
        """Виконує вхід і встановлює JWT для наступних запитів."""

        if not username or not username.strip():
            raise ValueError("Username cannot be empty")

        if not password:
            raise ValueError("Password cannot be empty")

        # Не залишаємо попередній токен під час нового входу.
        self.api_client.clear_access_token()

        response = self.api_client.post(
            "/auth/login",
            json={
                "username": username.strip(),
                "password": password,
            }
        )

        if not isinstance(response, dict):
            raise AuthenticationError(
                "Backend returned an invalid login response"
            )

        token = response.get("access_token")
        token_type = response.get("token_type", "bearer")

        if (
            not isinstance(token, str)
            or not token.strip()
            or token_type != "bearer"
        ):
            raise AuthenticationError(
                "Backend returned invalid authentication data"
            )

        self.api_client.set_access_token(token)

        return response

    def get_current_user(self) -> dict[str, Any]:
        """Отримує профіль авторизованого користувача."""

        if not self.api_client.is_authenticated:
            raise AuthenticationError(
                "User is not authenticated"
            )

        try:
            response = self.api_client.get("/auth/me")
        except APIRequestError as exc:
            if exc.status_code == 401:
                self.api_client.clear_access_token()
            raise

        if not isinstance(response, dict):
            raise AuthenticationError(
                "Backend returned an invalid user response"
            )

        return response

    def logout(self) -> None:
        """Відкликає JWT на Backend та очищає локальну сесію."""

        if not self.api_client.is_authenticated:
            return

        try:
            self.api_client.post("/auth/logout")
        except APIRequestError as exc:
            # Токен уже недійсний або відкликаний.
            if exc.status_code != 401:
                raise
        finally:
            # Навіть якщо Backend недоступний, локальний токен
            # більше не використовується.
            self.api_client.clear_access_token()

    @property
    def is_authenticated(self) -> bool:
        """Показує, чи встановлено локальний JWT."""

        return self.api_client.is_authenticated
