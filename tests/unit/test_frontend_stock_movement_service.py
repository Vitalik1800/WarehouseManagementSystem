from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from frontend.app.services.stock_movement_service import (
    StockMovementService,
    StockMovementServiceError,
)


@pytest.fixture
def api():
    client = Mock()
    client.is_authenticated = True
    return client


@pytest.fixture
def movement():
    return {
        "id": 7, "product_id": 2, "user_id": 3, "supplier_id": None,
        "movement_type": "issue", "quantity": "1.250",
        "created_at": "2026-10-17T09:00:00", "note": None,
    }


def test_create_receipt(api, movement):
    api.post.return_value = {**movement, "movement_type": "receipt", "supplier_id": 4}
    result = StockMovementService(api).create_receipt(2, "1.250", supplier_id=4, note=" delivery ")
    assert result["quantity"] == "1.250"
    api.post.assert_called_once_with(
        "/stock-movements/receipts",
        json={"product_id": 2, "movement_type": "receipt", "quantity": "1.250", "supplier_id": 4, "note": "delivery"},
    )


def test_create_issue(api, movement):
    api.post.return_value = movement
    StockMovementService(api).create_issue(2, "1")
    assert api.post.call_args.args == ("/stock-movements/issues",)


def test_writeoff_requires_reason(api):
    with pytest.raises(ValueError, match="причину"):
        StockMovementService(api).create_writeoff(2, 1, note="  ")
    api.post.assert_not_called()


def test_create_writeoff(api, movement):
    api.post.return_value = {**movement, "movement_type": "writeoff", "note": "Damaged"}
    StockMovementService(api).create_writeoff(2, "1", note=" Damaged ")
    assert api.post.call_args.kwargs["json"]["note"] == "Damaged"


@pytest.mark.parametrize("quantity", [0, -1, True, "NaN", "Infinity", "0.0001", "99999999999.9999", "abc"])
def test_bad_quantity(api, quantity):
    with pytest.raises(ValueError):
        StockMovementService(api).create_issue(2, quantity)
    api.post.assert_not_called()


@pytest.mark.parametrize("product_id", [0, -1, True, "1"])
def test_bad_id(api, product_id):
    with pytest.raises(ValueError):
        StockMovementService(api).create_issue(product_id, 1)


def test_list_filters(api, movement):
    api.get.return_value = [movement]
    result = StockMovementService(api).list_movements(
        0, 25, product_id=2, movement_type="issue", date_from=datetime(2026, 10, 1), sort_by="oldest"
    )
    assert result[0]["id"] == 7
    api.get.assert_called_once_with(
        "/stock-movements",
        params={"offset": 0, "limit": 25, "product_id": 2,
                "movement_type": "issue", "date_from": "2026-10-01T00:00:00", "sort_by": "oldest"},
    )


@pytest.mark.parametrize("offset,limit", [(-1, 50), (True, 50), (0, 0), (0, 101), (0, False)])
def test_bad_pagination(api, offset, limit):
    with pytest.raises(ValueError):
        StockMovementService(api).list_movements(offset, limit)


def test_timezone_rejected(api):
    with pytest.raises(ValueError):
        StockMovementService(api).list_movements(date_from=datetime.now(timezone.utc))


def test_date_range_rejected(api):
    with pytest.raises(ValueError):
        StockMovementService(api).list_movements(date_from=datetime(2026, 10, 2), date_to=datetime(2026, 10, 1))


def test_duplicate_ids_rejected(api, movement):
    api.get.return_value = [movement, movement]
    with pytest.raises(StockMovementServiceError, match="ID"):
        StockMovementService(api).list_movements()


def test_bad_response_rejected(api, movement):
    api.get.return_value = [{**movement, "quantity": "NaN"}]
    with pytest.raises(StockMovementServiceError):
        StockMovementService(api).list_movements()


def test_get_movement(api, movement):
    api.get.return_value = movement
    assert StockMovementService(api).get_movement(7)["id"] == 7
    api.get.assert_called_once_with("/stock-movements/7")


def test_get_movement_mismatch(api, movement):
    api.get.return_value = movement
    with pytest.raises(StockMovementServiceError):
        StockMovementService(api).get_movement(8)


def test_get_product_balance(api):
    api.get.return_value = {"product_id": 2, "sku": "A", "name": "Item", "unit": "pcs", "quantity": "0.000"}
    result = StockMovementService(api).get_product_balance(2)
    assert result["quantity"] == "0.000"
    api.get.assert_called_once_with("/stock-movements/products/2/balance")


def test_auth_required(api):
    api.is_authenticated = False
    with pytest.raises(StockMovementServiceError):
        StockMovementService(api).list_movements()
    api.get.assert_not_called()


def test_api_error_propagates(api):
    api.post.side_effect = RuntimeError("network")
    with pytest.raises(RuntimeError, match="network"):
        StockMovementService(api).create_issue(2, 1)
