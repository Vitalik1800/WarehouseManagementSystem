from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies.auth import get_current_user
from backend.app.main import app
from backend.app.models.stock_movement import StockMovement
from backend.app.models.user import User
from backend.app.services.inventory_service import (
    InventoryService,
    InsufficientStockError,
    StockMovementNotFoundError,
    StockProductNotFoundError,
    StockQuantityOverflowError,
    StockSupplierNotFoundError
)

from backend.app.schemas.stock_movements import StockBalanceResponse


@pytest.fixture
def client():
    original = dict(app.dependency_overrides)

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


@pytest.fixture
def authorize():
    def set_user(role="worker", user_id=7):
        user = User(
            id=user_id,
            name="Test User",
            username="testuser",
            password_hash="test",
            role=role,
            is_active=True,
        )

        app.dependency_overrides[get_current_user] = (
            lambda: user
        )

        return user

    return set_user


def make_movement(
    movement_type="receipt",
    movement_id=10,
    quantity="5.000",
):
    return StockMovement(
        id=movement_id,
        product_id=1,
        user_id=7,
        movement_type=movement_type,
        quantity=Decimal(quantity),
        created_at=datetime.now(timezone.utc),
        note=(
            "Damaged goods"
            if movement_type == "writeoff"
            else None
        ),
    )


@pytest.mark.parametrize(
    "method,path",
    [
        ("POST", "/stock-movements/receipts"),
        ("POST", "/stock-movements/issues"),
        ("POST", "/stock-movements/writeoffs"),
        ("GET", "/stock-movements"),
        ("GET", "/stock-movements/1"),
    ],
)
def test_unauthorized_access(client, method, path):
    response = client.request(
        method,
        path,
        json={
            "product_id": 1,
            "movement_type": "receipt",
            "quantity": "1.000",
        },
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role,expected",
    [
        ("admin", 200),
        ("worker", 200),
        ("guest", 403),
    ],
)
def test_list_role_access(
    client,
    authorize,
    role,
    expected,
):
    authorize(role=role)

    with patch.object(
        InventoryService,
        "list_movements",
        return_value=[],
    ):
        response = client.get("/stock-movements")

    assert response.status_code == expected


@pytest.mark.parametrize(
    "movement_type,path",
    [
        ("receipt", "receipts"),
        ("issue", "issues"),
        ("writeoff", "writeoffs"),
    ],
)
def test_create_movement_success(
    client,
    authorize,
    movement_type,
    path,
):
    authorize(user_id=7)

    movement = make_movement(movement_type)

    payload = {
        "product_id": 1,
        "movement_type": movement_type,
        "quantity": "5.000",
    }

    if movement_type == "writeoff":
        payload["note"] = "Damaged goods"

    with patch.object(
        InventoryService,
        "create_movement",
        return_value=movement,
    ) as mocked:
        response = client.post(
            f"/stock-movements/{path}",
            json=payload,
        )

    assert response.status_code == 201
    assert response.json()["movement_type"] == movement_type
    assert response.json()["user_id"] == 7
    assert response.json()["quantity"] == "5.000"

    mocked.assert_called_once()

    kwargs = mocked.call_args.kwargs

    assert kwargs["user_id"] == 7
    assert kwargs["data"].movement_type == movement_type


@pytest.mark.parametrize(
    "error,expected",
    [
        (StockProductNotFoundError("Missing product"), 404),
        (StockSupplierNotFoundError("Missing supplier"), 404),
        (InsufficientStockError("Insufficient stock"), 409),
        (StockQuantityOverflowError("Overflow"), 409),
    ],
)
def test_create_movement_domain_errors(
    client,
    authorize,
    error,
    expected,
):
    authorize()

    with patch.object(
        InventoryService,
        "create_movement",
        side_effect=error,
    ):
        response = client.post(
            "/stock-movements/receipts",
            json={
                "product_id": 1,
                "movement_type": "receipt",
                "quantity": "5.000",
            },
        )

    assert response.status_code == expected
    assert response.json()["detail"] == str(error)


@pytest.mark.parametrize(
    "path,movement_type",
    [
        ("receipts", "issue"),
        ("issues", "receipt"),
        ("writeoffs", "receipt"),
    ],
)
def test_reject_wrong_movement_type(
    client,
    authorize,
    path,
    movement_type,
):
    authorize()

    with patch.object(
        InventoryService,
        "create_movement",
    ) as mocked:
        response = client.post(
            f"/stock-movements/{path}",
            json={
                "product_id": 1,
                "movement_type": movement_type,
                "quantity": "1.000",
            },
        )

    assert response.status_code == 422
    mocked.assert_not_called()


@pytest.mark.parametrize(
    "quantity",
    [
        "0",
        "-1",
        "0.0001",
    ],
)
def test_reject_invalid_quantity(
    client,
    authorize,
    quantity,
):
    authorize()

    with patch.object(
        InventoryService,
        "create_movement",
    ) as mocked:
        response = client.post(
            "/stock-movements/receipts",
            json={
                "product_id": 1,
                "movement_type": "receipt",
                "quantity": quantity,
            },
        )

    assert response.status_code == 422
    mocked.assert_not_called()


def test_get_movement_success(client, authorize):
    authorize()

    movement = make_movement(movement_id=10)

    with patch.object(
        InventoryService,
        "get_movement",
        return_value=movement,
    ) as mocked:
        response = client.get("/stock-movements/10")

    assert response.status_code == 200
    assert response.json()["id"] == 10
    mocked.assert_called_once_with(10)


def test_get_movement_not_found(client, authorize):
    authorize()

    with patch.object(
        InventoryService,
        "get_movement",
        side_effect=StockMovementNotFoundError(
            "Movement not found"
        ),
    ):
        response = client.get("/stock-movements/999")

    assert response.status_code == 404


def test_list_movements_filters(client, authorize):
    authorize()

    with patch.object(
        InventoryService,
        "list_movements",
        return_value=[],
    ) as mocked:
        response = client.get(
            "/stock-movements",
            params={
                "offset": 10,
                "limit": 20,
                "product_id": 1,
                "user_id": 7,
                "supplier_id": 3,
                "movement_type": "receipt",
            },
        )

    assert response.status_code == 200
    assert response.json() == []

    mocked.assert_called_once_with(
        offset=10,
        limit=20,
        product_id=1,
        user_id=7,
        supplier_id=3,
        movement_type="receipt",
    )


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
        {"product_id": 0},
        {"movement_type": "transfer"},
    ],
)
def test_invalid_list_filters(
    client,
    authorize,
    params,
):
    authorize()

    with patch.object(
        InventoryService,
        "list_movements",
    ) as mocked:
        response = client.get(
            "/stock-movements",
            params=params,
        )

    assert response.status_code == 422
    mocked.assert_not_called()


# ============================================================
# Stage 7.7 — Stock Balance API tests
# ============================================================

BALANCE_URL = "/stock-movements/products/{product_id}/balance"


def make_stock_balance(
    product_id=1,
    quantity="125.375",
):
    return StockBalanceResponse(
        product_id=product_id,
        sku="SKU-001",
        name="Test Product",
        unit="pcs",
        quantity=Decimal(quantity),
    )


def test_stock_balance_success(client, authorize):
    authorize(role="worker")

    balance = make_stock_balance()

    with patch.object(
        InventoryService,
        "get_stock_balance",
        return_value=balance,
    ) as mocked:
        response = client.get(
            BALANCE_URL.format(product_id=1)
        )

    assert response.status_code == 200
    assert response.json() == {
        "product_id": 1,
        "sku": "SKU-001",
        "name": "Test Product",
        "unit": "pcs",
        "quantity": "125.375",
    }

    mocked.assert_called_once_with(1)


@pytest.mark.parametrize(
    "role,expected",
    [
        ("admin", 200),
        ("worker", 200),
        ("guest", 403),
    ],
)
def test_stock_balance_role_access(
    client,
    authorize,
    role,
    expected,
):
    authorize(role=role)

    with patch.object(
        InventoryService,
        "get_stock_balance",
        return_value=make_stock_balance(),
    ) as mocked:
        response = client.get(
            BALANCE_URL.format(product_id=1)
        )

    assert response.status_code == expected

    if expected == 200:
        mocked.assert_called_once_with(1)
    else:
        mocked.assert_not_called()


def test_stock_balance_unauthorized(client):
    with patch.object(
        InventoryService,
        "get_stock_balance",
    ) as mocked:
        response = client.get(
            BALANCE_URL.format(product_id=1)
        )

    assert response.status_code == 401
    mocked.assert_not_called()


def test_stock_balance_product_not_found(
    client,
    authorize,
):
    authorize(role="worker")

    with patch.object(
        InventoryService,
        "get_stock_balance",
        side_effect=StockProductNotFoundError(
            "Product not found"
        ),
    ) as mocked:
        response = client.get(
            BALANCE_URL.format(product_id=999)
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Product not found"

    mocked.assert_called_once_with(999)


@pytest.mark.parametrize(
    "product_id",
    [
        "0",
        "-1",
        "abc",
    ],
)
def test_stock_balance_invalid_product_id(
    client,
    authorize,
    product_id,
):
    authorize(role="worker")

    with patch.object(
        InventoryService,
        "get_stock_balance",
    ) as mocked:
        response = client.get(
            BALANCE_URL.format(product_id=product_id)
        )

    assert response.status_code == 422
    mocked.assert_not_called()


@pytest.mark.parametrize(
    "quantity",
    [
        "0.000",
        "0.001",
        "125.375",
        "99999999999.999",
    ],
)
def test_stock_balance_decimal_precision(
    client,
    authorize,
    quantity,
):
    authorize(role="worker")

    with patch.object(
        InventoryService,
        "get_stock_balance",
        return_value=make_stock_balance(
            quantity=quantity
        ),
    ):
        response = client.get(
            BALANCE_URL.format(product_id=1)
        )

    assert response.status_code == 200
    assert Decimal(
        response.json()["quantity"]
    ) == Decimal(quantity)


# ============================================================
# Stage 8.3 - Stock Movement Journal API tests
# ============================================================

def test_list_movements_date_range_and_sort(client, authorize):
    authorize(role="worker")

    date_from = datetime(2026, 10, 1, 8, 30)
    date_to = datetime(2026, 10, 14, 18, 45)

    with patch.object(
        InventoryService,
        "list_movements",
        return_value=[],
    ) as mocked:
        response = client.get(
            "/stock-movements",
            params={
                "offset": 5,
                "limit": 10,
                "product_id": 1,
                "user_id": 7,
                "supplier_id": 3,
                "movement_type": "receipt",
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat(),
                "sort_by": "oldest",
            },
        )

    assert response.status_code == 200
    assert response.json() == []

    mocked.assert_called_once_with(
        offset=5,
        limit=10,
        product_id=1,
        user_id=7,
        supplier_id=3,
        movement_type="receipt",
        date_from=date_from,
        date_to=date_to,
        sort_by="oldest",
    )


@pytest.mark.parametrize(
    "params,expected_key,expected_value",
    [
        (
            {"date_from": "2026-10-01T08:30:00"},
            "date_from",
            datetime(2026, 10, 1, 8, 30),
        ),
        (
            {"date_to": "2026-10-14T18:45:00"},
            "date_to",
            datetime(2026, 10, 14, 18, 45),
        ),
        (
            {"sort_by": "oldest"},
            "sort_by",
            "oldest",
        ),
    ],
)
def test_list_movements_optional_journal_filters(
    client,
    authorize,
    params,
    expected_key,
    expected_value,
):
    authorize(role="worker")

    with patch.object(
        InventoryService,
        "list_movements",
        return_value=[],
    ) as mocked:
        response = client.get(
            "/stock-movements",
            params=params,
        )

    assert response.status_code == 200
    assert mocked.call_args.kwargs[expected_key] == expected_value


@pytest.mark.parametrize(
    "params",
    [
        {"date_from": "invalid-date"},
        {"date_to": "not-a-date"},
        {
            "date_from": "2026-10-15T00:00:00",
            "date_to": "2026-10-14T00:00:00",
        },
        {"sort_by": "invalid"},
        {"sort_by": "NEWEST"},
        {"date_from": "2026-10-01T08:30:00Z"},
        {"date_to": "2026-10-14T18:45:00+03:00"},
    ],
)
def test_list_movements_invalid_journal_filters(
    client,
    authorize,
    params,
):
    authorize(role="worker")

    with patch.object(
        InventoryService,
        "list_movements",
    ) as mocked:
        response = client.get(
            "/stock-movements",
            params=params,
        )

    assert response.status_code == 422
    mocked.assert_not_called()
