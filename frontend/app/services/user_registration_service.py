from typing import Any

from frontend.app.api.client import APIClient, APIClientError


class UserRegistrationError(APIClientError):
    """Некоректна відповідь сервера під час створення користувача."""


class UserRegistrationService:
    """Створення користувачів адміністратором через API."""

    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    def register_user(
        self,
        name: str,
        username: str,
        password: str,
        role: str = "worker",
    ) -> dict[str, Any]:
        """Створює користувача через захищений POST /users."""

        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 150:
            raise ValueError("Ім'я повинно містити від 2 до 150 символів")

        if not isinstance(username, str):
            raise ValueError("Некоректний логін")

        username = username.strip()

        if not 3 <= len(username) <= 50:
            raise ValueError("Логін повинен містити від 3 до 50 символів")

        if not all(
            character in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
            for character in username
        ):
            raise ValueError("Логін містить недозволені символи")

        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise ValueError("Пароль повинен містити від 8 до 128 символів")

        if role not in ("admin", "worker"):
            raise ValueError("Недопустима роль користувача")

        if not self.api_client.is_authenticated:
            raise UserRegistrationError(
                "Для створення користувача необхідна авторизація"
            )

        response = self.api_client.post(
            "/users",
            json={
                "name": name.strip(),
                "username": username,
                "password": password,
                "role": role,
            },
        )

        if not isinstance(response, dict):
            raise UserRegistrationError(
                "Сервер повернув некоректну відповідь"
            )

        if not isinstance(response.get("id"), int) or isinstance(
            response.get("id"), bool
        ):
            raise UserRegistrationError(
                "Сервер не повернув коректний ID користувача"
            )

        return response
