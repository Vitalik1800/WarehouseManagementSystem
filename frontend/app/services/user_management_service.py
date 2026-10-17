from typing import Any

from frontend.app.api.client import APIClient


class UserManagementError(Exception):
    """Помилка обробки даних користувачів."""


class UserManagementService:
    """Сервіс адміністративного керування користувачами."""

    ALLOWED_ROLES = {"admin", "worker"}

    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    @classmethod
    def _validate_user(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise UserManagementError(
                "Некоректний формат даних користувача"
            )

        user_id = data.get("id")
        name = data.get("name")
        username = data.get("username")
        role = data.get("role")
        is_active = data.get("is_active")

        if type(user_id) is not int or user_id < 1:
            raise UserManagementError("Некоректний ID користувача")

        if not isinstance(name, str) or not name.strip():
            raise UserManagementError("Некоректне ім'я користувача")

        if not isinstance(username, str) or not username.strip():
            raise UserManagementError("Некоректний логін користувача")

        if role not in cls.ALLOWED_ROLES:
            raise UserManagementError("Некоректна роль користувача")

        if type(is_active) is not bool:
            raise UserManagementError("Некоректний статус користувача")

        return {
            "id": user_id,
            "name": name,
            "username": username,
            "role": role,
            "is_active": is_active,
        }

    def deactivate_user(
        self,
        user_id: int,
    ) -> dict[str, Any]:
        """Деактивує обліковий запис користувача."""

        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id має бути додатним цілим числом")

        if not self.api_client.is_authenticated:
            raise UserManagementError(
                "Для деактивації користувача потрібна авторизація"
            )

        response = self.api_client.patch(
            f"/users/{user_id}/deactivate"
        )

        user = self._validate_user(response)

        if user["id"] != user_id:
            raise UserManagementError(
                "API повернув дані іншого користувача"
            )

        if user["is_active"] is not False:
            raise UserManagementError(
                "API не підтвердив деактивацію користувача"
            )

        return user

    def activate_user(
        self,
        user_id: int,
    ) -> dict[str, Any]:
        """Активує обліковий запис користувача."""

        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id має бути додатним цілим числом")

        if not self.api_client.is_authenticated:
            raise UserManagementError(
                "Для активації користувача потрібна авторизація"
            )

        response = self.api_client.patch(
            f"/users/{user_id}/activate"
        )

        user = self._validate_user(response)

        if user["id"] != user_id:
            raise UserManagementError(
                "API повернув дані іншого користувача"
            )

        if user["is_active"] is not True:
            raise UserManagementError(
                "API не підтвердив активацію користувача"
            )

        return user

    def change_user_role(
        self,
        user_id: int,
        role: str,
    ) -> dict[str, Any]:
        """Змінює роль користувача."""

        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id має бути додатним цілим числом")

        if not isinstance(role, str) or role not in self.ALLOWED_ROLES:
            raise ValueError("Роль повинна бути admin або worker")

        if not self.api_client.is_authenticated:
            raise UserManagementError(
                "Для зміни ролі потрібна авторизація"
            )

        response = self.api_client.patch(
            f"/users/{user_id}/role",
            json={"role": role},
        )

        user = self._validate_user(response)

        if user["id"] != user_id:
            raise UserManagementError(
                "API повернув дані іншого користувача"
            )

        if user["role"] != role:
            raise UserManagementError(
                "API повернув роль, що не відповідає запиту"
            )

        return user

    def update_user(
        self,
        user_id: int,
        name: str | None = None,
        username: str | None = None,
    ) -> dict[str, Any]:
        """Оновлює ім'я та/або логін користувача."""

        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id має бути додатним цілим числом")

        if name is None and username is None:
            raise ValueError("Потрібно вказати хоча б одне поле")

        payload: dict[str, str] = {}

        if name is not None:
            if not isinstance(name, str):
                raise ValueError("Ім'я має бути рядком")

            name = name.strip()

            if not 2 <= len(name) <= 150:
                raise ValueError("Ім'я повинно містити 2-150 символів")

            payload["name"] = name

        if username is not None:
            if not isinstance(username, str):
                raise ValueError("Логін має бути рядком")

            username = username.strip()

            if not 3 <= len(username) <= 50:
                raise ValueError("Логін повинен містити 3-50 символів")

            if not all(
                char in "abcdefghijklmnopqrstuvwxyz"
                "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
                for char in username
            ):
                raise ValueError(
                    "Логін може містити лише латинські літери, "
                    "цифри та підкреслення"
                )

            payload["username"] = username

        if not self.api_client.is_authenticated:
            raise UserManagementError(
                "Для оновлення користувача потрібна авторизація"
            )

        response = self.api_client.patch(
            f"/users/{user_id}",
            json=payload,
        )

        user = self._validate_user(response)

        if user["id"] != user_id:
            raise UserManagementError(
                "API повернув дані іншого користувача"
            )

        return user

    def get_user(self, user_id: int) -> dict[str, Any]:
        """Отримує інформацію про користувача за ID."""

        if type(user_id) is not int or user_id < 1:
            raise ValueError("user_id має бути додатним цілим числом")

        if not self.api_client.is_authenticated:
            raise UserManagementError(
                "Для перегляду користувача потрібна авторизація"
            )

        response = self.api_client.get(f"/users/{user_id}")

        user = self._validate_user(response)

        if user["id"] != user_id:
            raise UserManagementError(
                "API повернув дані іншого користувача"
            )

        return user

    def list_users(
        self,
        offset: int = 0,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Отримує сторінку списку користувачів."""

        if type(offset) is not int or offset < 0:
            raise ValueError("offset має бути цілим числом >= 0")

        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit має бути від 1 до 100")

        if not self.api_client.is_authenticated:
            raise UserManagementError(
                "Для перегляду користувачів потрібна авторизація"
            )

        response = self.api_client.get(
            "/users",
            params={
                "offset": offset,
                "limit": limit,
            },
        )

        if not isinstance(response, list):
            raise UserManagementError(
                "API повернув некоректний список користувачів"
            )

        if len(response) > limit:
            raise UserManagementError(
                "API повернув більше користувачів, ніж запитано"
            )

        users = [self._validate_user(item) for item in response]

        ids = [user["id"] for user in users]

        if len(ids) != len(set(ids)):
            raise UserManagementError(
                "API повернув повторювані ID користувачів"
            )

        return users
