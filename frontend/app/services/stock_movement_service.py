"""Validated frontend API access for stock movements."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from frontend.app.api.client import APIClient


class StockMovementServiceError(Exception):
    """Invalid authentication state or unexpected stock API response."""


class StockMovementService:
    _TYPES = {"receipt", "issue", "writeoff"}

    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    def _auth(self) -> None:
        if not self.api_client.is_authenticated:
            raise StockMovementServiceError("Потрібна авторизація")

    @staticmethod
    def _id(value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("ID має бути додатним цілим числом")
        return value

    @staticmethod
    def _quantity(value: Any, *, positive: bool = True) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError("Некоректна кількість")
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Некоректна кількість") from exc
        if not amount.is_finite() or (amount <= 0 if positive else amount < 0):
            raise ValueError("Некоректна кількість")
        if amount.as_tuple().exponent < -3 or len(amount.as_tuple().digits) + max(amount.as_tuple().exponent, 0) > 14:
            raise ValueError("Кількість має містити не більше 14 цифр і 3 знаків після коми")
        if amount.adjusted() >= 11:
            raise ValueError("Кількість перевищує допустиму")
        return str(amount)

    @staticmethod
    def _note(value: str | None) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("Примітка має бути рядком")
        return value.strip() or None

    @classmethod
    def _movement(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise StockMovementServiceError("Некоректна відповідь API: операція")
        try:
            result = dict(data)
            for field in ("id", "product_id", "user_id"):
                result[field] = cls._id(data[field])
            supplier_id = data["supplier_id"]
            result["supplier_id"] = None if supplier_id is None else cls._id(supplier_id)
            movement_type = data["movement_type"]
            if movement_type not in cls._TYPES:
                raise ValueError("Невідомий тип операції")
            result["movement_type"] = movement_type
            result["quantity"] = cls._quantity(data["quantity"])
            result["note"] = cls._note(data["note"])
            timestamp = data["created_at"]
            if not isinstance(timestamp, str):
                raise ValueError("Некоректна дата операції")
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            result["created_at"] = timestamp
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise StockMovementServiceError(f"Некоректні дані операції: {exc}") from exc
        return result

    def _create(self, movement_type: str, product_id: int, quantity: Any,
                *, supplier_id: int | None = None, note: str | None = None) -> dict[str, Any]:
        self._id(product_id)
        normalized_quantity = self._quantity(quantity)
        normalized_note = self._note(note)
        if supplier_id is not None:
            self._id(supplier_id)
            if movement_type != "receipt":
                raise ValueError("Постачальник дозволений лише для надходження")
        if movement_type == "writeoff" and not normalized_note:
            raise ValueError("Для списання необхідно вказати причину")
        payload = {"product_id": product_id, "movement_type": movement_type,
                   "quantity": normalized_quantity, "supplier_id": supplier_id,
                   "note": normalized_note}
        self._auth()
        endpoint = {"receipt": "receipts", "issue": "issues", "writeoff": "writeoffs"}[movement_type]
        result = self._movement(self.api_client.post(f"/stock-movements/{endpoint}", json=payload))
        if result["product_id"] != product_id or result["movement_type"] != movement_type:
            raise StockMovementServiceError("API повернув іншу складську операцію")
        return result

    def create_receipt(self, product_id: int, quantity: Any, *,
                       supplier_id: int | None = None, note: str | None = None) -> dict[str, Any]:
        return self._create("receipt", product_id, quantity, supplier_id=supplier_id, note=note)

    def create_issue(self, product_id: int, quantity: Any, *, note: str | None = None) -> dict[str, Any]:
        return self._create("issue", product_id, quantity, note=note)

    def create_writeoff(self, product_id: int, quantity: Any, *, note: str) -> dict[str, Any]:
        return self._create("writeoff", product_id, quantity, note=note)

    def list_movements(self, offset: int = 0, limit: int = 50, *,
                       product_id: int | None = None, user_id: int | None = None,
                       supplier_id: int | None = None, movement_type: str | None = None,
                       date_from: datetime | None = None, date_to: datetime | None = None,
                       sort_by: str = "newest") -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0:
            raise ValueError("offset має бути невід'ємним цілим числом")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit має бути від 1 до 100")
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        for key, value in (("product_id", product_id), ("user_id", user_id), ("supplier_id", supplier_id)):
            if value is not None:
                params[key] = self._id(value)
        if movement_type is not None:
            if movement_type not in self._TYPES:
                raise ValueError("Невідомий тип операції")
            params["movement_type"] = movement_type
        for key, value in (("date_from", date_from), ("date_to", date_to)):
            if value is not None:
                if not isinstance(value, datetime) or value.tzinfo is not None:
                    raise ValueError(f"{key} має бути datetime без часового поясу")
                params[key] = value.isoformat()
        if date_from is not None and date_to is not None and date_from > date_to:
            raise ValueError("date_from не може бути пізніше за date_to")
        if sort_by not in ("newest", "oldest"):
            raise ValueError("Невідомий порядок сортування")
        if sort_by != "newest":
            params["sort_by"] = sort_by
        self._auth()
        data = self.api_client.get("/stock-movements", params=params)
        if not isinstance(data, list) or len(data) > limit:
            raise StockMovementServiceError("Некоректний список операцій")
        result = [self._movement(item) for item in data]
        if len({item["id"] for item in result}) != len(result):
            raise StockMovementServiceError("Повторювані ID операцій")
        return result

    def get_movement(self, movement_id: int) -> dict[str, Any]:
        self._id(movement_id)
        self._auth()
        result = self._movement(self.api_client.get(f"/stock-movements/{movement_id}"))
        if result["id"] != movement_id:
            raise StockMovementServiceError("API повернув іншу операцію")
        return result

    def get_product_balance(self, product_id: int) -> dict[str, Any]:
        self._id(product_id)
        self._auth()
        data = self.api_client.get(f"/stock-movements/products/{product_id}/balance")
        if not isinstance(data, dict):
            raise StockMovementServiceError("Некоректний залишок товару")
        try:
            result = dict(data)
            result["product_id"] = self._id(data["product_id"])
            for field in ("sku", "name", "unit"):
                if not isinstance(data[field], str):
                    raise ValueError(f"Некоректне поле {field}")
            result["quantity"] = self._quantity(data["quantity"], positive=False)
            if result["product_id"] != product_id:
                raise ValueError("API повернув інший товар")
        except (KeyError, ValueError, TypeError) as exc:
            raise StockMovementServiceError(f"Некоректний залишок товару: {exc}") from exc
        return result
