from typing import Any
from frontend.app.api.client import APIClient

class WarehouseClientServiceError(Exception):
    pass

class WarehouseClientService:
    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    def _auth(self) -> None:
        if not self.api_client.is_authenticated:
            raise WarehouseClientServiceError("Потрібна авторизація")

    @staticmethod
    def _validate(item: Any) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise WarehouseClientServiceError("Некоректна відповідь API")
        wid, name, code = item.get("id"), item.get("name"), item.get("code")
        desc, active = item.get("description"), item.get("is_active")
        if type(wid) is not int or wid < 1 or not isinstance(name, str) or not 1 <= len(name.strip()) <= 100 or not isinstance(code, str) or not 1 <= len(code.strip()) <= 30 or (desc is not None and not isinstance(desc, str)) or type(active) is not bool:
            raise WarehouseClientServiceError("Некоректні дані складу")
        return {"id": wid, "name": name, "code": code, "description": desc, "is_active": active}

    @staticmethod
    def _required(value: str, max_len: int, label: str) -> str:
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= max_len:
            raise ValueError(f"{label}: від 1 до {max_len} символів")
        return value.strip()

    def list_warehouses(self, offset: int = 0, limit: int = 50) -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("Некоректна пагінація")
        self._auth()
        result = self.api_client.get("/warehouses", params={"offset": offset, "limit": limit})
        if not isinstance(result, list) or len(result) > limit:
            raise WarehouseClientServiceError("Некоректний список складів")
        rows = [self._validate(row) for row in result]
        if len({row['id'] for row in rows}) != len(rows):
            raise WarehouseClientServiceError("Повторювані ID")
        return rows

    def create_warehouse(self, name: str, code: str, description: str | None, is_active: bool) -> dict[str, Any]:
        name = self._required(name, 100, "Назва")
        code = self._required(code, 30, "Код")
        if description is not None and not isinstance(description, str):
            raise ValueError("Некоректний опис")
        if type(is_active) is not bool:
            raise ValueError("Некоректний статус")
        self._auth()
        return self._validate(self.api_client.post("/warehouses", json={"name": name, "code": code, "description": description, "is_active": is_active}))

    def update_warehouse(self, warehouse_id: int, name: str, code: str, description: str | None, is_active: bool) -> dict[str, Any]:
        self._check_id(warehouse_id)
        name = self._required(name, 100, "Назва")
        code = self._required(code, 30, "Код")
        if description is not None and not isinstance(description, str):
            raise ValueError("Некоректний опис")
        if type(is_active) is not bool:
            raise ValueError("Некоректний статус")
        self._auth()
        result = self._validate(self.api_client.patch(f"/warehouses/{warehouse_id}", json={"name": name, "code": code, "description": description, "is_active": is_active}))
        if result['id'] != warehouse_id:
            raise WarehouseClientServiceError("API повернув інший ID")
        return result

    @staticmethod
    def _check_id(warehouse_id: int) -> None:
        if type(warehouse_id) is not int or warehouse_id < 1:
            raise ValueError("Некоректний ID")

    def delete_warehouse(self, warehouse_id: int) -> None:
        self._check_id(warehouse_id)
        self._auth()
        self.api_client.delete(f"/warehouses/{warehouse_id}")
