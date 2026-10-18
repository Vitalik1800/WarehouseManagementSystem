from decimal import Decimal
from uuid import uuid4

import pytest

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.app.api.dependencies.auth import get_current_user
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import Category, Product, StorageLocation
from backend.app.models.supplier import Supplier
from backend.app.models.user import User


DASHBOARD_URL = "/dashboard/summary"


@pytest.fixture
def client(db_session):
    original_overrides = dict(app.dependency_overrides)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides.pop(get_current_user, None)

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
            name="Dashboard Integration User",
            username="dashboard_test_user",
            password_hash="test",
            role=role,
            is_active=True
        )

        app.dependency_overrides[get_current_user] = lambda: user

        return user

    return set_user


@pytest.fixture
def dashboard_data(db_session, main_warehouse_id):
    marker = uuid4().hex[:12]

    category = Category(
        name=f"DashboardCategory_{marker}",
    )

    location = StorageLocation(
        name=f"DashboardLocation_{marker}",
     warehouse_id=main_warehouse_id,)

    supplier = Supplier(
        name=f"DashboardSupplier_{marker}",
    )

    db_session.add_all([
        category,
        location,
        supplier
    ])
    db_session.flush()

    products = [
        Product(
            sku=f"DASH_ZERO_{marker}",
            name=f"Dashboard Zero {marker}",
            unit="pcs",
            quantity=Decimal("0.000"),
            category_id=category.id,
            location_id=location.id
        ),
        Product(
            sku=f"DASH_LOW_{marker}",
            name=f"Dashboard Low {marker}",
            unit="pcs",
            quantity=Decimal("5.250"),
            category_id=category.id,
            location_id=location.id
        ),
        Product(
            sku=f"DASH_HIGH_{marker}",
            name=f"Dashboard High {marker}",
            unit="pcs",
            quantity=Decimal("100.000"),
            category_id=category.id,
            location_id=location.id
        )
    ]

    db_session.add_all(products)
    db_session.flush()

    return {
        "category": category,
        "location": location,
        "supplier": supplier,
        "products": products
    }


def database_counts(db_session):
    def count(model, *conditions):
        statement = select(func.count()).select_from(model)

        if conditions:
            statement = statement.where(*conditions)

        return int(db_session.scalar(statement) or 0)

    return {
        "total_products": count(Product),
        "total_categories": count(Category),
        "total_suppliers": count(Supplier),
        "total_locations": count(StorageLocation),
        "in_stock_products": count(
            Product,
            Product.quantity > 0,
        ),
        "out_of_stock_products": count(
            Product,
            Product.quantity == 0,
        )
    }


def test_dashboard_requires_authentication(client):
    response = client.get(DASHBOARD_URL)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role,expected_status",
    [
        ("admin", 200),
        ("worker", 200),
        ("guest", 403)
    ]
)
def test_dashboard_role_access(
    client,
    authorize,
    role,
    expected_status
):
    authorize(role)

    response = client.get(DASHBOARD_URL)

    assert response.status_code == expected_status


def test_dashboard_returns_correct_statistics(
    client,
    authorize,
    dashboard_data,
    db_session
):
    authorize("admin")

    expected = database_counts(db_session)

    response = client.get(DASHBOARD_URL)

    assert response.status_code == 200, response.text
    assert response.json() == expected

    result = response.json()

    assert result["total_products"] >= 3
    assert result["total_categories"] >= 1
    assert result["total_suppliers"] >= 1
    assert result["total_locations"] >= 1
    assert result["in_stock_products"] >= 2
    assert result["out_of_stock_products"] >= 1

    assert (
        result["in_stock_products"]
        + result["out_of_stock_products"]
        == result["total_products"]
    )


def test_dashboard_worker_sees_same_statistics(
    client,
    authorize,
    dashboard_data,
    db_session
):
    expected = database_counts(db_session)

    authorize("worker")

    response = client.get(DASHBOARD_URL)

    assert response.status_code == 200, response.text
    assert response.json() == expected


def test_dashboard_empty_database_counts(
    client,
    authorize,
    db_session
):
    authorize("admin")

    expected = database_counts(db_session)

    response = client.get(DASHBOARD_URL)

    assert response.status_code == 200, response.text
    assert response.json() == expected

    assert all(
        isinstance(value, int) and value >= 0
        for value in response.json().values()
    )


def test_dashboard_get_does_not_modify_products(
    client,
    authorize,
    dashboard_data,
    db_session
):
    authorize("worker")

    original_quantities = {
        product.id: product.quantity
        for product in dashboard_data["products"]
    }

    response = client.get(DASHBOARD_URL)

    assert response.status_code == 200, response.text

    db_session.expire_all()

    for product in dashboard_data["products"]:
        refreshed = db_session.get(Product, product.id)

        assert refreshed.quantity == original_quantities[product.id]


def test_dashboard_response_has_expected_fields(
    client,
    authorize
):
    authorize("admin")

    response = client.get(DASHBOARD_URL)

    assert response.status_code == 200, response.text

    assert set(response.json()) == {
        "total_products",
        "total_categories",
        "total_suppliers",
        "total_locations",
        "in_stock_products",
        "out_of_stock_products"
    }
