from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import (
    Category,
    Product,
    StorageLocation,
    User,
)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def admin_headers(db_session):
    user = User(
        name="Product Administrator",
        username=f"prod_admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def worker_headers(db_session):
    user = User(
        name="Product Worker",
        username=f"prod_worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def product_data(db_session, main_warehouse_id):
    suffix = uuid4().hex[:12]

    category = Category(name=f"ProductCategory_{suffix}")
    location = StorageLocation(name=f"ProductLocation_{suffix}", warehouse_id=main_warehouse_id)

    db_session.add_all([category, location])
    db_session.flush()

    product = Product(
        sku=f"PRODUCT-{suffix}",
        name="Existing Product",
        unit="pcs",
        quantity=Decimal("0.000"),
        category_id=category.id,
        location_id=location.id,
    )

    db_session.add(product)
    db_session.flush()

    return {
        "product": product,
        "category": category,
        "location": location,
    }


def create_payload(product_data, sku=None):
    return {
        "sku": sku or f"NEW-{uuid4().hex[:12]}",
        "name": "New Product",
        "unit": "pcs",
        "category_id": product_data["category"].id,
        "location_id": product_data["location"].id,
    }


# ============================================================
# RBAC: ADMIN
# ============================================================


def test_admin_can_list_products(client, admin_headers):
    response = client.get("/products", headers=admin_headers)

    assert response.status_code == 200, response.text


def test_admin_can_get_product(client, admin_headers, product_data):
    product = product_data["product"]

    response = client.get(
        f"/products/{product.id}",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == product.id


def test_admin_can_create_product(
    client, admin_headers, product_data
):
    response = client.post(
        "/products",
        json=create_payload(product_data),
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text


def test_admin_can_update_product(
    client, admin_headers, product_data
):
    product = product_data["product"]

    response = client.patch(
        f"/products/{product.id}",
        json={"name": "Updated Product"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Updated Product"


def test_admin_can_delete_product(
    client, admin_headers, product_data, db_session
):
    product_id = product_data["product"].id

    response = client.delete(
        f"/products/{product_id}",
        headers=admin_headers,
    )

    assert response.status_code == 204, response.text

    db_session.expire_all()
    assert db_session.get(Product, product_id) is None


# ============================================================
# RBAC: WORKER
# ============================================================


def test_worker_can_list_products(client, worker_headers):
    response = client.get("/products", headers=worker_headers)

    assert response.status_code == 200, response.text


def test_worker_can_get_product(
    client, worker_headers, product_data
):
    product = product_data["product"]

    response = client.get(
        f"/products/{product.id}",
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text


def test_worker_cannot_create_product(
    client, worker_headers, product_data
):
    response = client.post(
        "/products",
        json=create_payload(product_data),
        headers=worker_headers,
    )

    assert response.status_code == 403


def test_worker_cannot_update_product(
    client, worker_headers, product_data
):
    product = product_data["product"]
    original_name = product.name

    response = client.patch(
        f"/products/{product.id}",
        json={"name": "Forbidden Update"},
        headers=worker_headers,
    )

    assert response.status_code == 403
    assert product.name == original_name


def test_worker_cannot_delete_product(
    client, worker_headers, product_data, db_session
):
    product_id = product_data["product"].id

    response = client.delete(
        f"/products/{product_id}",
        headers=worker_headers,
    )

    assert response.status_code == 403

    db_session.expire_all()
    assert db_session.get(Product, product_id) is not None


# ============================================================
# UNAUTHORIZED REQUESTS
# ============================================================


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/products", None),
        ("get", "/products/1", None),
        ("post", "/products", {}),
        ("patch", "/products/1", {}),
        ("delete", "/products/1", None),
    ],
)
def test_missing_token_returns_401(client, method, path, payload):
    response = client.request(
        method.upper(),
        path,
        json=payload,
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


# ============================================================
# SKU UNIQUENESS
# ============================================================


def test_create_duplicate_sku_returns_409(
    client, admin_headers, product_data
):
    existing = product_data["product"]

    response = client.post(
        "/products",
        json=create_payload(product_data, sku=existing.sku),
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text


def test_update_duplicate_sku_returns_409(
    client, admin_headers, product_data, db_session
):
    existing = product_data["product"]

    another = Product(
        sku=f"SECOND-{uuid4().hex[:12]}",
        name="Second Product",
        unit="pcs",
        quantity=Decimal("0.000"),
        category_id=product_data["category"].id,
        location_id=product_data["location"].id,
    )

    db_session.add(another)
    db_session.flush()

    response = client.patch(
        f"/products/{another.id}",
        json={"sku": existing.sku},
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text


# ============================================================
# FOREIGN KEY VALIDATION
# ============================================================


def test_create_invalid_category_returns_404(
    client, admin_headers, product_data
):
    payload = create_payload(product_data)
    payload["category_id"] = 2147483647

    response = client.post(
        "/products",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text


def test_create_invalid_location_returns_404(
    client, admin_headers, product_data
):
    payload = create_payload(product_data)
    payload["location_id"] = 2147483647

    response = client.post(
        "/products",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text


def test_update_invalid_category_returns_404(
    client, admin_headers, product_data
):
    product = product_data["product"]

    response = client.patch(
        f"/products/{product.id}",
        json={"category_id": 2147483647},
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text


def test_update_invalid_location_returns_404(
    client, admin_headers, product_data
):
    product = product_data["product"]

    response = client.patch(
        f"/products/{product.id}",
        json={"location_id": 2147483647},
        headers=admin_headers,
    )

    assert response.status_code == 404, response.text


# ============================================================
# DATABASE CONSTRAINTS
# ============================================================


def test_database_rejects_duplicate_sku(db_session, product_data):
    existing = product_data["product"]

    duplicate = Product(
        sku=existing.sku,
        name="Duplicate SKU",
        unit="pcs",
        quantity=Decimal("0.000"),
        category_id=product_data["category"].id,
        location_id=product_data["location"].id,
    )

    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_invalid_category(db_session, product_data):
    product = Product(
        sku=f"INVALID-CAT-{uuid4().hex[:12]}",
        name="Invalid Category Product",
        unit="pcs",
        quantity=Decimal("0.000"),
        category_id=2147483647,
        location_id=product_data["location"].id,
    )

    db_session.add(product)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_database_rejects_invalid_location(db_session, product_data):
    product = Product(
        sku=f"INVALID-LOC-{uuid4().hex[:12]}",
        name="Invalid Location Product",
        unit="pcs",
        quantity=Decimal("0.000"),
        category_id=product_data["category"].id,
        location_id=2147483647,
    )

    db_session.add(product)

    with pytest.raises(IntegrityError):
        db_session.flush()
