from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.category import Category
from backend.app.models.user import User

from backend.app.models.product import Product
from backend.app.models.storage_location import StorageLocation


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
    admin = User(
        name="Category Administrator",
        username=f"cat_admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    db_session.add(admin)
    db_session.flush()

    token = create_access_token(user_id=admin.id)

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def worker_headers(db_session):
    worker = User(
        name="Category Worker",
        username=f"cat_worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add(worker)
    db_session.flush()

    token = create_access_token(user_id=worker.id)

    return {"Authorization": f"Bearer {token}"}


def test_list_categories_admin_success(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"Electronics_{uuid4().hex[:12]}",
        description="Electronic products",
    )

    db_session.add(category)
    db_session.flush()

    response = client.get(
        "/categories",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert isinstance(data, list)
    assert any(
        item["id"] == category.id
        and item["name"] == category.name
        for item in data
    )


def test_list_categories_worker_success(
        client,
        db_session,
        worker_headers,
):
    category = Category(
        name=f"Furniture_{uuid4().hex[:12]}",
        description="Furniture products",
    )

    db_session.add(category)
    db_session.flush()

    response = client.get(
        "/categories",
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text

    assert any(
        item["id"] == category.id
        for item in response.json()
    )


def test_get_category_by_id_admin_success(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"Tools_{uuid4().hex[:12]}",
        description="Warehouse tools",
    )

    db_session.add(category)
    db_session.flush()

    response = client.get(
        f"/categories/{category.id}",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == category.id
    assert data["name"] == category.name
    assert data["description"] == category.description


def test_get_category_by_id_worker_success(
        client,
        db_session,
        worker_headers,
):
    category = Category(
        name=f"Clothing_{uuid4().hex[:12]}",
        description="Clothing products",
    )

    db_session.add(category)
    db_session.flush()

    response = client.get(
        f"/categories/{category.id}",
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == category.id


def test_list_categories_missing_token(client):
    response = client.get("/categories")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_get_category_by_id_not_found(
        client,
        admin_headers,
):
    response = client.get(
        "/categories/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_category_admin_success(
        client,
        db_session,
        admin_headers,
):
    name = f"NewCategory_{uuid4().hex[:12]}"

    response = client.post(
        "/categories",
        json={
            "name": name,
            "description": "New category description",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert isinstance(data["id"], int)
    assert data["name"] == name
    assert data["description"] == "New category description"

    db_session.expire_all()

    saved_category = db_session.get(Category, data["id"])

    assert saved_category is not None
    assert saved_category.name == name


def test_create_category_duplicate_name(
        client,
        db_session,
        admin_headers,
):
    name = f"Duplicate_{uuid4().hex[:12]}"

    existing = Category(
        name=name,
        description="Original category",
    )

    db_session.add(existing)
    db_session.flush()

    response = client.post(
        "/categories",
        json={
            "name": name,
            "description": "Duplicate category",
        },
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text

    db_session.refresh(existing)
    assert existing.description == "Original category"


def test_create_category_worker_forbidden(
        client,
        db_session,
        worker_headers,
):
    name = f"Forbidden_{uuid4().hex[:12]}"

    response = client.post(
        "/categories",
        json={"name": name},
        headers=worker_headers,
    )

    assert response.status_code == 403

    assert not db_session.query(Category).filter_by(
        name=name
    ).first()


def test_create_category_missing_token(client):
    response = client.post(
        "/categories",
        json={"name": "Unauthorized Category"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"name": "A" * 101},
        {"name": "Valid", "unknown_field": "value"},
    ],
)
def test_create_category_invalid_payload(
        client,
        admin_headers,
        payload,
):
    response = client.post(
        "/categories",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


def test_update_category_admin_success(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"Original_{uuid4().hex[:12]}",
        description="Original description",
    )
    db_session.add(category)
    db_session.flush()

    category_id = category.id
    new_name = f"Updated_{uuid4().hex[:12]}"

    response = client.patch(
        f"/categories/{category_id}",
        json={
            "name": new_name,
            "description": "Updated description",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == new_name
    assert response.json()["description"] == "Updated description"

    db_session.expire_all()
    updated = db_session.get(Category, category_id)

    assert updated.name == new_name
    assert updated.description == "Updated description"


def test_update_category_partial_description(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"Partial_{uuid4().hex[:12]}",
        description="Before",
    )
    db_session.add(category)
    db_session.flush()

    response = client.patch(
        f"/categories/{category.id}",
        json={"description": "After"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == category.name
    assert response.json()["description"] == "After"


def test_update_category_duplicate_name(
        client,
        db_session,
        admin_headers,
):
    first = Category(name=f"First_{uuid4().hex[:12]}")
    second = Category(name=f"Second_{uuid4().hex[:12]}")

    db_session.add_all([first, second])
    db_session.flush()

    response = client.patch(
        f"/categories/{second.id}",
        json={"name": first.name},
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text

    db_session.refresh(second)
    assert second.name != first.name


def test_update_category_not_found(
        client,
        admin_headers,
):
    response = client.patch(
        "/categories/2147483647",
        json={"name": "Updated"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_category_worker_forbidden(
        client,
        db_session,
        worker_headers,
):
    category = Category(name=f"Protected_{uuid4().hex[:12]}")
    db_session.add(category)
    db_session.flush()

    original_name = category.name

    response = client.patch(
        f"/categories/{category.id}",
        json={"name": "Unauthorized Update"},
        headers=worker_headers,
    )

    assert response.status_code == 403

    db_session.refresh(category)
    assert category.name == original_name


def test_update_category_missing_token(client):
    response = client.patch(
        "/categories/1",
        json={"name": "Unauthorized"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"name": None},
        {"name": ""},
        {"name": "   "},
        {"name": "A" * 101},
        {"unknown_field": "value"},
    ],
)
def test_update_category_invalid_payload(
        client,
        db_session,
        admin_headers,
        payload,
):
    category = Category(name=f"Validation_{uuid4().hex[:12]}")
    db_session.add(category)
    db_session.flush()

    response = client.patch(
        f"/categories/{category.id}",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


def test_update_category_empty_payload(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"Unchanged_{uuid4().hex[:12]}",
        description="Original",
    )
    db_session.add(category)
    db_session.flush()

    response = client.patch(
        f"/categories/{category.id}",
        json={},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == category.name
    assert response.json()["description"] == "Original"


def test_delete_category_admin_success(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"Delete_{uuid4().hex[:12]}",
        description="Category to delete",
    )
    db_session.add(category)
    db_session.flush()

    category_id = category.id

    response = client.delete(
        f"/categories/{category_id}",
        headers=admin_headers,
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    db_session.expire_all()

    assert db_session.get(Category, category_id) is None


def test_delete_category_not_found(
        client,
        admin_headers,
):
    response = client.delete(
        "/categories/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_delete_category_worker_forbidden(
        client,
        db_session,
        worker_headers,
):
    category = Category(
        name=f"ProtectedDelete_{uuid4().hex[:12]}",
    )
    db_session.add(category)
    db_session.flush()

    category_id = category.id

    response = client.delete(
        f"/categories/{category_id}",
        headers=worker_headers,
    )

    assert response.status_code == 403

    db_session.expire_all()

    assert db_session.get(Category, category_id) is not None


def test_delete_category_missing_token(client):
    response = client.delete("/categories/1")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_delete_category_with_products_conflict(
        client,
        db_session,
        admin_headers, main_warehouse_id,
):
    suffix = uuid4().hex[:12]

    category = Category(
        name=f"CategoryWithProduct_{suffix}",
        description="Category containing a product",
    )

    location = StorageLocation(
        name=f"Storage_{suffix}",
        description="Test storage location",
     warehouse_id=main_warehouse_id,)

    db_session.add_all([category, location])
    db_session.flush()

    product = Product(
        sku=f"SKU-{suffix}",
        name="Test product",
        unit="pcs",
        category_id=category.id,
        location_id=location.id,
    )

    db_session.add(product)
    db_session.flush()

    category_id = category.id
    product_id = product.id

    response = client.delete(
        f"/categories/{category_id}",
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text

    db_session.expire_all()

    saved_category = db_session.get(Category, category_id)
    saved_product = db_session.get(Product, product_id)

    assert saved_category is not None
    assert saved_product is not None
    assert saved_product.category_id == category_id


def test_list_categories_pagination(
        client,
        db_session,
        admin_headers,
):
    suffix = uuid4().hex[:12]

    categories = [
        Category(name=f"Pagination_{suffix}_{index}")
        for index in range(3)
    ]

    db_session.add_all(categories)
    db_session.flush()

    response = client.get(
        "/categories",
        params={"offset": 0, "limit": 2},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2


def test_list_categories_large_offset(
        client,
        admin_headers,
):
    response = client.get(
        "/categories",
        params={"offset": 2147483647, "limit": 10},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == []


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": -1},
        {"limit": 101},
        {"offset": "invalid"},
        {"limit": "invalid"},
    ],
)
def test_list_categories_invalid_pagination(
        client,
        admin_headers,
        params,
):
    response = client.get(
        "/categories",
        params=params,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


def test_list_categories_limit_one(
        client,
        admin_headers,
):
    response = client.get(
        "/categories",
        params={"offset": 0, "limit": 1},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) <= 1


def test_list_categories_limit_one_hundred(
        client,
        admin_headers,
):
    response = client.get(
        "/categories",
        params={"offset": 0, "limit": 100},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) <= 100


# ============================================================
# ADDITIONAL CATEGORY INTEGRATION TESTS
# ============================================================


def test_update_category_same_name_success(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"SameName_{uuid4().hex[:12]}",
        description="Original description",
    )

    db_session.add(category)
    db_session.flush()

    category_id = category.id
    original_name = category.name

    response = client.patch(
        f"/categories/{category_id}",
        json={"name": original_name},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == original_name

    db_session.expire_all()

    saved = db_session.get(Category, category_id)

    assert saved is not None
    assert saved.name == original_name


def test_update_category_clear_description(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"ClearDescription_{uuid4().hex[:12]}",
        description="Description to clear",
    )

    db_session.add(category)
    db_session.flush()

    category_id = category.id

    response = client.patch(
        f"/categories/{category_id}",
        json={"description": None},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["description"] is None

    db_session.expire_all()

    saved = db_session.get(Category, category_id)

    assert saved is not None
    assert saved.description is None


def test_get_category_by_id_missing_token(client):
    response = client.get(
        "/categories/1",
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_list_categories_nonzero_offset(
        client,
        db_session,
        admin_headers,
):
    suffix = uuid4().hex[:12]

    categories = [
        Category(name=f"Offset_{suffix}_{index}")
        for index in range(3)
    ]

    db_session.add_all(categories)
    db_session.flush()

    # Determine the expected page from the complete ordered list.
    all_response = client.get(
        "/categories",
        params={"offset": 0, "limit": 100},
        headers=admin_headers,
    )

    assert all_response.status_code == 200, all_response.text

    all_items = all_response.json()

    # Use the last two records, which include the newly created
    # categories when their IDs are the highest.
    offset = max(0, len(all_items) - 2)

    response = client.get(
        "/categories",
        params={"offset": offset, "limit": 2},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    expected_ids = [
        item["id"]
        for item in all_items[offset:offset + 2]
    ]

    actual_ids = [
        item["id"]
        for item in response.json()
    ]

    assert actual_ids == expected_ids


def test_create_category_name_trimmed(
        client,
        db_session,
        admin_headers,
):
    name = f"TrimmedCreate_{uuid4().hex[:12]}"

    response = client.post(
        "/categories",
        json={
            "name": f"   {name}   ",
            "description": "Whitespace validation",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == name

    db_session.expire_all()

    saved = db_session.get(
        Category,
        response.json()["id"],
    )

    assert saved is not None
    assert saved.name == name


def test_update_category_name_trimmed(
        client,
        db_session,
        admin_headers,
):
    category = Category(
        name=f"BeforeTrim_{uuid4().hex[:12]}",
    )

    db_session.add(category)
    db_session.flush()

    category_id = category.id
    new_name = f"AfterTrim_{uuid4().hex[:12]}"

    response = client.patch(
        f"/categories/{category_id}",
        json={"name": f"   {new_name}   "},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == new_name

    db_session.expire_all()

    saved = db_session.get(Category, category_id)

    assert saved is not None
    assert saved.name == new_name
