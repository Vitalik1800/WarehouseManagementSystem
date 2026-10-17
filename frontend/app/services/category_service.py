from typing import Any

from frontend.app.api.client import APIClient


class CategoryServiceError(Exception):
    """Помилка обробки даних категорій."""


_UNSET = object()


class CategoryService:
    """Сервіс керування категоріями товарів."""

    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    @staticmethod
    def _validate_category(data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise CategoryServiceError("Некоректний формат категорії")
        category_id = data.get("id")
        name = data.get("name")
        description = data.get("description")
        if type(category_id) is not int or category_id < 1:
            raise CategoryServiceError("Некоректний ID категорії")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise CategoryServiceError("Некоректна назва категорії")
        if description is not None and not isinstance(description, str):
            raise CategoryServiceError("Некоректний опис категорії")
        return {"id": category_id, "name": name, "description": description}

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str):
            raise ValueError("Назва категорії має бути рядком")
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("Назва повинна містити 1–100 символів")
        return name

    @staticmethod
    def _validate_description(description: str | None) -> str | None:
        if description is not None and not isinstance(description, str):
            raise ValueError("Опис категорії має бути рядком або None")
        return description

    def _require_auth(self) -> None:
        if not self.api_client.is_authenticated:
            raise CategoryServiceError("Потрібна авторизація")

    def list_categories(self, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0:
            raise ValueError("offset має бути цілим числом >= 0")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit має бути від 1 до 100")
        self._require_auth()
        response = self.api_client.get("/categories", params={"offset": offset, "limit": limit})
        if not isinstance(response, list) or len(response) > limit:
            raise CategoryServiceError("Некоректний список категорій")
        categories = [self._validate_category(item) for item in response]
        ids = [item["id"] for item in categories]
        if len(ids) != len(set(ids)):
            raise CategoryServiceError("Повторювані ID категорій")
        return categories

    def get_category(self, category_id: int) -> dict[str, Any]:
        if type(category_id) is not int or category_id < 1:
            raise ValueError("Некоректний ID категорії")
        self._require_auth()
        category = self._validate_category(self.api_client.get(f"/categories/{category_id}"))
        if category["id"] != category_id:
            raise CategoryServiceError("API повернув іншу категорію")
        return category

    def create_category(self, name: str, description: str | None = None) -> dict[str, Any]:
        name = self._validate_name(name)
        description = self._validate_description(description)
        self._require_auth()
        return self._validate_category(self.api_client.post("/categories", json={"name": name, "description": description}))

    def update_category(
        self,
        category_id: int,
        name: str | None = None,
        description: str | None | object = _UNSET,
    ) -> dict[str, Any]:
        if type(category_id) is not int or category_id < 1:
            raise ValueError("Некоректний ID категорії")
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = self._validate_name(name)
        if description is not _UNSET:
            payload["description"] = self._validate_description(description)
        if not payload:
            raise ValueError("Потрібно вказати хоча б одне поле")
        self._require_auth()
        category = self._validate_category(self.api_client.patch(f"/categories/{category_id}", json=payload))
        if category["id"] != category_id:
            raise CategoryServiceError("API повернув іншу категорію")
        return category

    def delete_category(self, category_id: int) -> None:
        if type(category_id) is not int or category_id < 1:
            raise ValueError("Некоректний ID категорії")
        self._require_auth()
        self.api_client.delete(f"/categories/{category_id}")
