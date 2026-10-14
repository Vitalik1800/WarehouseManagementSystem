
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies.auth import get_current_user
from backend.app.main import app
from backend.app.models.user import User
from backend.app.services.stock_balance_service import (
    StockBalanceService
)


BALANCES_URL = "/stock-balances"


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


def make_product(
    product_id=1,
    quantity="125.375",
):
    from types import SimpleNamespace

    return SimpleNamespace(
        id=product_id,
        sku=f"SKU-{product_id:03d}",
        name=f"Test Product {product_id}",
        unit="pcs",
        quantity=Decimal(quantity),
        category_id=2,
        location_id=3,
    )


def test_stock_balances_unauthorized(client):
    with patch.object(
        StockBalanceService,
        "list_stock_balances",
    ) as mocked:
        response = client.get(BALANCES_URL)

    assert response.status_code == 401
    mocked.assert_not_called()


@pytest.mark.parametrize(
    "role,expected",
    [
        ("admin", 200),
        ("worker", 200),
        ("guest", 403),
    ],
)
def test_stock_balances_role_access(
    client,
    authorize,
    role,
    expected,
):
    authorize(role=role)

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
        return_value=[],
    ) as mocked:
        response = client.get(BALANCES_URL)

    assert response.status_code == expected

    if expected == 200:
        mocked.assert_called_once()
    else:
        mocked.assert_not_called()


def test_stock_balances_empty_list(client, authorize):
    authorize()

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
        return_value=[],
    ):
        response = client.get(BALANCES_URL)

    assert response.status_code == 200
    assert response.json() == []


def test_stock_balances_success(client, authorize):
    authorize()

    products = [
        make_product(1, "125.375"),
        make_product(2, "0.000"),
    ]

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
        return_value=products,
    ):
        response = client.get(BALANCES_URL)

    assert response.status_code == 200

    assert response.json() == [
        {
            "id": 1,
            "sku": "SKU-001",
            "name": "Test Product 1",
            "unit": "pcs",
            "quantity": "125.375",
            "category_id": 2,
            "location_id": 3,
        },
        {
            "id": 2,
            "sku": "SKU-002",
            "name": "Test Product 2",
            "unit": "pcs",
            "quantity": "0.000",
            "category_id": 2,
            "location_id": 3,
        },
    ]


def test_stock_balances_default_parameters(
    client,
    authorize,
):
    authorize()

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
        return_value=[],
    ) as mocked:
        response = client.get(BALANCES_URL)

    assert response.status_code == 200

    mocked.assert_called_once_with(
        offset=0,
        limit=50,
        stock_status=None,
        category_id=None,
        location_id=None,
        search=None,
        min_quantity=None,
        max_quantity=None,
        sort_by="id",
    )


def test_stock_balances_all_filters(
    client,
    authorize,
):
    authorize()

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
        return_value=[],
    ) as mocked:
        response = client.get(
            BALANCES_URL,
            params={
                "offset": 10,
                "limit": 20,
                "stock_status": "in_stock",
                "category_id": 2,
                "location_id": 3,
                "search": "SKU",
                "min_quantity": "1.250",
                "max_quantity": "100.500",
                "sort_by": "quantity_desc",
            },
        )

    assert response.status_code == 200

    mocked.assert_called_once_with(
        offset=10,
        limit=20,
        stock_status="in_stock",
        category_id=2,
        location_id=3,
        search="SKU",
        min_quantity=Decimal("1.250"),
        max_quantity=Decimal("100.500"),
        sort_by="quantity_desc",
    )


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
        {"category_id": 0},
        {"location_id": 0},
        {"stock_status": "invalid"},
        {"sort_by": "unknown"},
        {"min_quantity": "-1"},
        {"max_quantity": "-1"},
        {"min_quantity": "NaN"},
        {"max_quantity": "Infinity"},
        {"min_quantity": "abc"},
        {"max_quantity": "abc"},
        {
            "min_quantity": "10",
            "max_quantity": "5",
        },
    ],
)
def test_stock_balances_invalid_filters(
    client,
    authorize,
    params,
):
    authorize()

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
    ) as mocked:
        response = client.get(
            BALANCES_URL,
            params=params,
        )

    assert response.status_code == 422
    mocked.assert_not_called()


@pytest.mark.parametrize(
    "sort_by",
    [
        "id",
        "quantity_asc",
        "quantity_desc",
    ],
)
def test_stock_balances_sort_options(
    client,
    authorize,
    sort_by,
):
    authorize()

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
        return_value=[],
    ) as mocked:
        response = client.get(
            BALANCES_URL,
            params={"sort_by": sort_by},
        )

    assert response.status_code == 200
    assert mocked.call_args.kwargs["sort_by"] == sort_by


@pytest.mark.parametrize(
    "stock_status",
    [
        "in_stock",
        "out_of_stock",
    ],
)
def test_stock_balances_status_options(
    client,
    authorize,
    stock_status,
):
    authorize()

    with patch.object(
        StockBalanceService,
        "list_stock_balances",
        return_value=[],
    ) as mocked:
        response = client.get(
            BALANCES_URL,
            params={"stock_status": stock_status},
        )

    assert response.status_code == 200
    assert (
        mocked.call_args.kwargs["stock_status"]
        == stock_status
    )
