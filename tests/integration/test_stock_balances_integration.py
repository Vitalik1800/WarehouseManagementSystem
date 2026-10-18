from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies.auth import get_current_user
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import Category, Product, StorageLocation
from backend.app.models.user import User


BALANCES_URL = "/stock-balances"


@pytest.fixture
def client(db_session):
    original_overrides = dict(app.dependency_overrides)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)


@pytest.fixture
def authorize():
    def set_user(role="worker"):
        user = User(
            id=7,
            name="Integration Test User",
            username="stock_balance_test_user",
            password_hash="test",
            role=role,
            is_active=True,
        )

        app.dependency_overrides[get_current_user] = (
            lambda: user
        )

        return user

    return set_user


@pytest.fixture
def stock_data(db_session, main_warehouse_id):
    marker = uuid4().hex[:12]

    category_a = Category(
        name=f"BalanceCategoryA_{marker}"
    )
    category_b = Category(
        name=f"BalanceCategoryB_{marker}"
    )

    location_a = StorageLocation(
        name=f"BalanceLocationA_{marker}"
    , warehouse_id=main_warehouse_id)
    location_b = StorageLocation(
        name=f"BalanceLocationB_{marker}"
    , warehouse_id=main_warehouse_id)

    db_session.add_all([
        category_a,
        category_b,
        location_a,
        location_b,
    ])
    db_session.flush()

    products = [
        Product(
            sku=f"BAL_ZERO_{marker}",
            name=f"Balance Zero {marker}",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category_a.id,
            location_id=location_a.id,
        ),
        Product(
            sku=f"BAL_LOW_{marker}",
            name=f"Balance Low {marker}",
            unit="pcs",
            quantity=Decimal("5.250"),
            category_id=category_a.id,
            location_id=location_a.id,
        ),
        Product(
            sku=f"BAL_MEDIUM_{marker}",
            name=f"Balance Medium {marker}",
            unit="pcs",
            quantity=Decimal("25.500"),
            category_id=category_a.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"BAL_HIGH_{marker}",
            name=f"Balance High {marker}",
            unit="pcs",
            quantity=Decimal("100.000"),
            category_id=category_b.id,
            location_id=location_b.id,
        ),
        Product(
            sku=f"BAL_TIE_{marker}",
            name=f"Balance Tie {marker}",
            unit="pcs",
            quantity=Decimal("25.500"),
            category_id=category_b.id,
            location_id=location_a.id,
        ),
    ]

    db_session.add_all(products)
    db_session.flush()

    return {
        "marker": marker,
        "products": products,
        "category_a": category_a,
        "category_b": category_b,
        "location_a": location_a,
        "location_b": location_b,
    }


def get_created_balances(client, stock_data, **params):
    response = client.get(
        BALANCES_URL,
        params=params,
    )

    assert response.status_code == 200, response.text

    created_ids = {
        product.id
        for product in stock_data["products"]
    }

    return [
        item
        for item in response.json()
        if item["id"] in created_ids
    ]


def test_unauthorized_access(client):
    response = client.get(BALANCES_URL)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role,expected",
    [
        ("admin", 200),
        ("worker", 200),
        ("guest", 403),
    ],
)
def test_role_access(
    client,
    authorize,
    role,
    expected,
):
    authorize(role)

    response = client.get(BALANCES_URL)

    assert response.status_code == expected


def test_response_contains_real_balances(
    client,
    authorize,
    stock_data,
):
    authorize()

    products = stock_data["products"]

    response = client.get(
        BALANCES_URL,
        params={
            "search": stock_data["marker"],
            "limit": 100,
        },
    )

    assert response.status_code == 200, response.text

    balances = response.json()

    assert len(balances) == 5

    by_id = {
        item["id"]: item
        for item in balances
    }

    for product in products:
        item = by_id[product.id]

        assert item["sku"] == product.sku
        assert item["name"] == product.name
        assert item["unit"] == product.unit
        assert Decimal(item["quantity"]) == product.quantity
        assert item["category_id"] == product.category_id
        assert item["location_id"] == product.location_id


@pytest.mark.parametrize(
    "stock_status,expected_indexes",
    [
        ("in_stock", [1, 2, 3, 4]),
        ("out_of_stock", [0]),
    ],
)
def test_stock_status_filter(
    client,
    authorize,
    stock_data,
    stock_status,
    expected_indexes,
):
    authorize()

    products = stock_data["products"]

    result = get_created_balances(
        client,
        stock_data,
        stock_status=stock_status,
        search=stock_data["marker"],
    )

    assert {item["id"] for item in result} == {
        products[index].id
        for index in expected_indexes
    }


def test_category_filter(
    client,
    authorize,
    stock_data,
):
    authorize()

    result = get_created_balances(
        client,
        stock_data,
        category_id=stock_data["category_a"].id,
        search=stock_data["marker"],
    )

    assert {item["id"] for item in result} == {
        stock_data["products"][0].id,
        stock_data["products"][1].id,
        stock_data["products"][2].id,
    }


def test_location_filter(
    client,
    authorize,
    stock_data,
):
    authorize()

    result = get_created_balances(
        client,
        stock_data,
        location_id=stock_data["location_b"].id,
        search=stock_data["marker"],
    )

    assert {item["id"] for item in result} == {
        stock_data["products"][2].id,
        stock_data["products"][3].id,
    }


def test_combined_filters(
    client,
    authorize,
    stock_data,
):
    authorize()

    result = get_created_balances(
        client,
        stock_data,
        stock_status="in_stock",
        category_id=stock_data["category_a"].id,
        location_id=stock_data["location_a"].id,
        min_quantity="5.000",
        max_quantity="6.000",
        search=stock_data["marker"],
    )

    assert [item["id"] for item in result] == [
        stock_data["products"][1].id
    ]


def test_quantity_range(
    client,
    authorize,
    stock_data,
):
    authorize()

    result = get_created_balances(
        client,
        stock_data,
        min_quantity="5.250",
        max_quantity="25.500",
        search=stock_data["marker"],
    )

    assert {item["id"] for item in result} == {
        stock_data["products"][1].id,
        stock_data["products"][2].id,
        stock_data["products"][4].id,
    }


@pytest.mark.parametrize(
    "sort_by,expected_indexes",
    [
        ("id", [0, 1, 2, 3, 4]),
        ("quantity_asc", [0, 1, 2, 4, 3]),
        ("quantity_desc", [3, 2, 4, 1, 0]),
    ],
)
def test_sorting(
    client,
    authorize,
    stock_data,
    sort_by,
    expected_indexes,
):
    authorize()

    result = get_created_balances(
        client,
        stock_data,
        search=stock_data["marker"],
        sort_by=sort_by,
    )

    assert [item["id"] for item in result] == [
        stock_data["products"][index].id
        for index in expected_indexes
    ]


def test_pagination(
    client,
    authorize,
    stock_data,
):
    authorize()

    first_page = get_created_balances(
        client,
        stock_data,
        search=stock_data["marker"],
        offset=0,
        limit=2,
    )

    second_page = get_created_balances(
        client,
        stock_data,
        search=stock_data["marker"],
        offset=2,
        limit=2,
    )

    assert len(first_page) == 2
    assert len(second_page) == 2

    assert {
        item["id"] for item in first_page
    }.isdisjoint({
        item["id"] for item in second_page
    })


def test_large_offset_returns_empty(
    client,
    authorize,
    stock_data,
):
    authorize()

    result = get_created_balances(
        client,
        stock_data,
        search=stock_data["marker"],
        offset=1000000,
    )

    assert result == []


def test_search_by_sku(
    client,
    authorize,
    stock_data,
):
    authorize()

    product = stock_data["products"][1]

    result = get_created_balances(
        client,
        stock_data,
        search=product.sku,
    )

    assert [item["id"] for item in result] == [
        product.id
    ]


def test_search_case_insensitive(
    client,
    authorize,
    stock_data,
):
    authorize()

    product = stock_data["products"][3]

    result = get_created_balances(
        client,
        stock_data,
        search=product.name.lower(),
    )

    assert [item["id"] for item in result] == [
        product.id
    ]


def test_empty_result(
    client,
    authorize,
    stock_data,
):
    authorize()

    result = get_created_balances(
        client,
        stock_data,
        search=f"NOT_FOUND_{stock_data['marker']}",
    )

    assert result == []


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
        {"stock_status": "invalid"},
        {"sort_by": "unknown"},
        {"min_quantity": "-1"},
        {"max_quantity": "Infinity"},
        {"min_quantity": "10", "max_quantity": "5"},
    ],
)
def test_invalid_parameters(
    client,
    authorize,
    params,
):
    authorize()

    response = client.get(
        BALANCES_URL,
        params=params,
    )

    assert response.status_code == 422


def test_get_does_not_change_quantities(
    client,
    authorize,
    stock_data,
    db_session,
):
    authorize()

    products = stock_data["products"]

    original = {
        product.id: product.quantity
        for product in products
    }

    response = client.get(
        BALANCES_URL,
        params={
            "search": stock_data["marker"],
        },
    )

    assert response.status_code == 200, response.text

    db_session.expire_all()

    for product in products:
        refreshed = db_session.get(
            Product,
            product.id,
        )

        assert refreshed.quantity == original[product.id]
