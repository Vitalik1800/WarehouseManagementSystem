"""Validated frontend access to the stock-balances API."""

from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from frontend.app.api.client import APIClient


class StockBalanceServiceError(Exception):
    """The stock-balances API returned unexpected data or auth is missing."""


StockStatus = Literal["in_stock", "out_of_stock"]
SortBy = Literal["id", "quantity_asc", "quantity_desc"]


class StockBalanceService:
    def __init__(self, api_client: APIClient) -> None:
        self.api_client = api_client

    @staticmethod
    def _id(value: int) -> int:
        if type(value) is not int or value <= 0:
            raise ValueError("ID must be a positive integer")
        return value

    @staticmethod
    def _quantity(value: Any, *, nonnegative: bool = True) -> str:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError("Quantity must be numeric")
        try:
            quantity = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Quantity must be numeric") from exc
        if not quantity.is_finite():
            raise ValueError("Quantity must be finite")
        if nonnegative and quantity < 0:
            raise ValueError("Quantity cannot be negative")
        if quantity.as_tuple().exponent < -3:
            raise ValueError("Quantity supports at most three decimal places")
        if len(quantity.as_tuple().digits) + max(quantity.as_tuple().exponent, 0) > 14:
            raise ValueError("Quantity exceeds supported precision")
        return str(quantity)

    @classmethod
    def _validate_balance(cls, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise StockBalanceServiceError("Invalid stock balance response")
        try:
            result = {"id": cls._id(data["id"])}
            for field in ("sku", "name", "unit"):
                value = data[field]
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"Invalid {field}")
                result[field] = value.strip()
            result["quantity"] = cls._quantity(data["quantity"])
            result["category_id"] = cls._id(data["category_id"])
            result["location_id"] = cls._id(data["location_id"])
        except (KeyError, ValueError, TypeError) as exc:
            raise StockBalanceServiceError(f"Invalid stock balance response: {exc}") from exc
        return result

    def list_balances(
        self,
        offset: int = 0,
        limit: int = 50,
        *,
        stock_status: StockStatus | None = None,
        category_id: int | None = None,
        location_id: int | None = None,
        search: str | None = None,
        min_quantity: str | int | float | Decimal | None = None,
        max_quantity: str | int | float | Decimal | None = None,
        sort_by: SortBy = "id",
    ) -> list[dict[str, Any]]:
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a nonnegative integer")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if stock_status is not None and stock_status not in ("in_stock", "out_of_stock"):
            raise ValueError("Invalid stock status")
        if sort_by not in ("id", "quantity_asc", "quantity_desc"):
            raise ValueError("Invalid sort order")

        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if stock_status is not None:
            params["stock_status"] = stock_status
        if category_id is not None:
            params["category_id"] = self._id(category_id)
        if location_id is not None:
            params["location_id"] = self._id(location_id)
        if search is not None:
            if not isinstance(search, str):
                raise ValueError("search must be a string")
            if search.strip():
                params["search"] = search.strip()
        if min_quantity is not None:
            params["min_quantity"] = self._quantity(min_quantity)
        if max_quantity is not None:
            params["max_quantity"] = self._quantity(max_quantity)
        if (
            min_quantity is not None
            and max_quantity is not None
            and Decimal(params["min_quantity"]) > Decimal(params["max_quantity"])
        ):
            raise ValueError("min_quantity cannot exceed max_quantity")
        params["sort_by"] = sort_by

        if not self.api_client.is_authenticated:
            raise StockBalanceServiceError("Authentication required")
        data = self.api_client.get("/stock-balances", params=params)
        if not isinstance(data, list) or len(data) > limit:
            raise StockBalanceServiceError("Invalid stock balance list response")
        balances = [self._validate_balance(item) for item in data]
        if len({item["id"] for item in balances}) != len(balances):
            raise StockBalanceServiceError("Duplicate product IDs in stock balances")
        return balances
