"""Unit tests for the frontend stock-balance service."""

from unittest.mock import Mock

import pytest

from frontend.app.api.client import APIConnectionError, APIRequestError
from frontend.app.services.stock_balance_service import (
    StockBalanceService,
    StockBalanceServiceError,
)


@pytest.fixture
def api():
    client = Mock()
    client.is_authenticated = True
    return client


@pytest.fixture
def balance():
    return {
        "id": 1,
        "sku": "SKU-1",
        "name": "Product",
        "unit": "pcs",
        "quantity": "12.500",
        "category_id": 2,
        "location_id": 3,
    }


def test_list_balances(api, balance):
    api.get.return_value = [balance]
    result = StockBalanceService(api).list_balances()
    assert result == [balance]
    api.get.assert_called_once_with(
        "/stock-balances", params={"offset": 0, "limit": 50, "sort_by": "id"}
    )


def test_all_filters(api, balance):
    api.get.return_value = [balance]
    result = StockBalanceService(api).list_balances(
        10, 25, stock_status="in_stock", category_id=2, location_id=3,
        search=" SKU ", min_quantity="1.250", max_quantity="20",
        sort_by="quantity_desc",
    )
    assert result[0]["id"] == 1
    api.get.assert_called_once_with(
        "/stock-balances",
        params={
            "offset": 10, "limit": 25, "stock_status": "in_stock",
            "category_id": 2, "location_id": 3, "search": "SKU",
            "min_quantity": "1.250", "max_quantity": "20",
            "sort_by": "quantity_desc",
        },
    )


def test_empty_search_omitted(api):
    api.get.return_value = []
    StockBalanceService(api).list_balances(search="  ")
    assert "search" not in api.get.call_args.kwargs["params"]


@pytest.mark.parametrize("offset,limit", [(-1, 50), (True, 50), (0, 0), (0, 101), (0, False)])
def test_bad_pagination(api, offset, limit):
    with pytest.raises(ValueError):
        StockBalanceService(api).list_balances(offset, limit)
    api.get.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("stock_status", "unknown"), ("category_id", 0), ("category_id", True),
    ("location_id", -1), ("sort_by", "newest"), ("search", 123),
    ("min_quantity", -1), ("min_quantity", "NaN"),
    ("max_quantity", "Infinity"), ("max_quantity", True),
    ("max_quantity", "0.0001"),
])
def test_bad_filters(api, field, value):
    with pytest.raises(ValueError):
        StockBalanceService(api).list_balances(**{field: value})
    api.get.assert_not_called()


def test_bad_quantity_range(api):
    with pytest.raises(ValueError):
        StockBalanceService(api).list_balances(min_quantity="10", max_quantity="9")
    api.get.assert_not_called()


def test_auth_required(api):
    api.is_authenticated = False
    with pytest.raises(StockBalanceServiceError):
        StockBalanceService(api).list_balances()
    api.get.assert_not_called()


@pytest.mark.parametrize("response", [None, {}, "bad", [1] * 51])
def test_invalid_list_response(api, response):
    api.get.return_value = response
    with pytest.raises(StockBalanceServiceError):
        StockBalanceService(api).list_balances()


@pytest.mark.parametrize("field,value", [
    ("id", True), ("sku", " "), ("name", None), ("unit", ""),
    ("quantity", "NaN"), ("quantity", "0.0001"),
    ("category_id", 0), ("location_id", False),
])
def test_invalid_balance_fields(api, balance, field, value):
    api.get.return_value = [{**balance, field: value}]
    with pytest.raises(StockBalanceServiceError):
        StockBalanceService(api).list_balances()


def test_missing_field(api, balance):
    del balance["location_id"]
    api.get.return_value = [balance]
    with pytest.raises(StockBalanceServiceError):
        StockBalanceService(api).list_balances()


def test_duplicate_ids(api, balance):
    api.get.return_value = [balance, balance.copy()]
    with pytest.raises(StockBalanceServiceError):
        StockBalanceService(api).list_balances()


@pytest.mark.parametrize("error", [APIConnectionError("offline"), APIRequestError(403, "Forbidden")])
def test_api_errors_propagate(api, error):
    api.get.side_effect = error
    with pytest.raises(type(error)):
        StockBalanceService(api).list_balances()


def test_quantity_string_preserves_decimal_precision(api, balance):
    api.get.return_value = [{**balance, "quantity": "0.001"}]
    assert StockBalanceService(api).list_balances()[0]["quantity"] == "0.001"
