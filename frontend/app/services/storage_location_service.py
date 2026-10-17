from typing import Any

from frontend.app.api.client import APIClient


class StorageLocationServiceError(Exception):
    """Помилка обробки даних місць зберігання."""


_UNSET = object()


class StorageLocationClientService:
    """Сервіс керування категоріями товарів."""

    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    @staticmethod
    def _validate_location(data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise StorageLocationServiceError("Некоректний формат місця зберігання")
        location_id = data.get("id")
        name = data.get("name")
        description = data.get("description")
        if type(location_id) is not int or location_id < 1:
            raise StorageLocationServiceError("Некоректний ID місця зберігання")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise StorageLocationServiceError("Некоректна назва місця зберігання")
        if description is not None and not isinstance(description, str):
            raise StorageLocationServiceError("Некоректний опис місця зберігання")
        return {"id": location_id, "name": name, "description": description}

    @staticmethod
    def _validate_name(name: str) -> str:
        if not isinstance(name, str):
            raise ValueError("Назва місця зберігання має бути рядком")
        name = name.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("Назва повинна містити 1–100 символів")
        return name

    @staticmethod
    def _validate_description(description: str | None) -> str | None:
        if description is not None and not isinstance(description, str):
            raise ValueError("Опис місця зберігання має бути рядком або None")
        return description

    def _require_auth(self) -> None:
        if not self.api_client.is_authenticated:
            raise StorageLocationServiceError("Потрібна авторизація")

    def list_locations(self, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0:
            raise ValueError("offset має бути цілим числом >= 0")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit має бути від 1 до 100")
        self._require_auth()
        response = self.api_client.get("/storage-locations", params={"offset": offset, "limit": limit})
        if not isinstance(response, list) or len(response) > limit:
            raise StorageLocationServiceError("Некоректний список місць зберігання")
        locations = [self._validate_location(item) for item in response]
        ids = [item["id"] for item in locations]
        if len(ids) != len(set(ids)):
            raise StorageLocationServiceError("Повторювані ID місць зберігання")
        return locations

    def get_location(self, location_id: int) -> dict[str, Any]:
        if type(location_id) is not int or location_id < 1:
            raise ValueError("Некоректний ID місця зберігання")
        self._require_auth()
        location = self._validate_location(self.api_client.get(f"/storage-locations/{location_id}"))
        if location["id"] != location_id:
            raise StorageLocationServiceError("API повернув іншу місце зберігання")
        return location

    def create_location(self, name: str, description: str | None = None) -> dict[str, Any]:
        name = self._validate_name(name)
        description = self._validate_description(description)
        self._require_auth()
        return self._validate_location(self.api_client.post("/storage-locations", json={"name": name, "description": description}))

    def update_location(
        self,
        location_id: int,
        name: str | None = None,
        description: str | None | object = _UNSET,
    ) -> dict[str, Any]:
        if type(location_id) is not int or location_id < 1:
            raise ValueError("Некоректний ID місця зберігання")
        payload: dict[str, Any] = {}
        if name is not None:
            payload["name"] = self._validate_name(name)
        if description is not _UNSET:
            payload["description"] = self._validate_description(description)
        if not payload:
            raise ValueError("Потрібно вказати хоча б одне поле")
        self._require_auth()
        location = self._validate_location(self.api_client.patch(f"/storage-locations/{location_id}", json=payload))
        if location["id"] != location_id:
            raise StorageLocationServiceError("API повернув іншу місце зберігання")
        return location

    def delete_location(self, location_id: int) -> None:
        if type(location_id) is not int or location_id < 1:
            raise ValueError("Некоректний ID місця зберігання")
        self._require_auth()
        self.api_client.delete(f"/storage-locations/{location_id}")
