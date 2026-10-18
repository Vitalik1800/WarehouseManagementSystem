from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import Category, Product, StorageLocation, User


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
        name="CRUD Administrator",
        username=f"crud_admin_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="admin",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    token = create_access_token(user_id=user.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def product_references(db_session, main_warehouse_id):
    suffix = uuid4().hex[:12]

    category_a = Category(name=f"CRUDCategoryA_{suffix}")
    category_b = Category(name=f"CRUDCategoryB_{suffix}")
    location_a = StorageLocation(name=f"CRUDLocationA_{suffix}", warehouse_id=main_warehouse_id)
    location_b = StorageLocation(name=f"CRUDLocationB_{suffix}", warehouse_id=main_warehouse_id)

    db_session.add_all([
        category_a,
        category_b,
        location_a,
        location_b,
    ])
    db_session.flush()

    return {
        "category_a": category_a,
        "category_b": category_b,
        "location_a": location_a,
        "location_b": location_b,
    }


def make_payload(references, **overrides):
    payload = {
        "sku": f"CRUD-{uuid4().hex[:12]}",
        "name": "Integration Product",
        "unit": "pcs",
        "description": "Original description",
        "category_id": references["category_a"].id,
        "location_id": references["location_a"].id,
    }
    payload.update(overrides)
    return payload


def create_product(client, admin_headers, references, **overrides):
    response = client.post(
        "/products",
        json=make_payload(references, **overrides),
        headers=admin_headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# ============================================================
# CREATE
# ============================================================


def test_create_product_persists_all_fields(
    client, admin_headers, product_references, db_session
):
    payload = make_payload(product_references)

    response = client.post(
        "/products",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    body = response.json()
    product_id = body["id"]

    assert body["sku"] == payload["sku"]
    assert body["name"] == payload["name"]
    assert body["unit"] == payload["unit"]
    assert body["description"] == payload["description"]
    assert body["category_id"] == payload["category_id"]
    assert body["location_id"] == payload["location_id"]
    assert Decimal(str(body["quantity"])) == Decimal("0.000")

    db_session.expire_all()
    stored = db_session.get(Product, product_id)

    assert stored is not None
    assert stored.sku == payload["sku"]
    assert stored.name == payload["name"]
    assert stored.quantity == Decimal("0.000")


def test_create_product_uses_defaults(
    client, admin_headers, product_references
):
    payload = make_payload(product_references)
    payload.pop("unit")
    payload.pop("description")

    response = client.post(
        "/products",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    body = response.json()
    assert body["unit"] == "pcs"
    assert body["description"] is None
    assert Decimal(str(body["quantity"])) == Decimal("0.000")


def test_create_product_trims_text(
    client, admin_headers, product_references
):
    sku = f"TRIM-{uuid4().hex[:12]}"
    payload = make_payload(
        product_references,
        sku=f"  {sku}  ",
        name="  Trimmed Product  ",
        unit="  kg  ",
        description="  Trimmed description  ",
    )

    response = client.post(
        "/products",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    body = response.json()
    assert body["sku"] == sku
    assert body["name"] == "Trimmed Product"
    assert body["unit"] == "kg"
    assert body["description"] == "Trimmed description"


# ============================================================
# READ
# ============================================================


def test_get_created_product(
    client, admin_headers, product_references
):
    created = create_product(
        client, admin_headers, product_references
    )

    response = client.get(
        f"/products/{created['id']}",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == created


def test_list_contains_created_product(
    client, admin_headers, product_references
):
    created = create_product(
        client, admin_headers, product_references
    )

    response = client.get(
        "/products",
        params={"sku": created["sku"]},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()] == [
        created["id"]
    ]


def test_get_missing_product_returns_404(
    client, admin_headers
):
    response = client.get(
        "/products/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


# ============================================================
# UPDATE
# ============================================================


def test_patch_name_preserves_other_fields(
    client, admin_headers, product_references, db_session
):
    created = create_product(
        client, admin_headers, product_references
    )

    response = client.patch(
        f"/products/{created['id']}",
        json={"name": "Updated Name"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    updated = response.json()
    assert updated["name"] == "Updated Name"

    for field in (
        "sku", "unit", "description",
        "category_id", "location_id", "quantity"
    ):
        assert updated[field] == created[field]

    db_session.expire_all()
    assert db_session.get(Product, created["id"]).name == "Updated Name"


def test_patch_multiple_fields(
    client, admin_headers, product_references
):
    created = create_product(
        client, admin_headers, product_references
    )

    new_sku = f"UPDATED-{uuid4().hex[:12]}"

    response = client.patch(
        f"/products/{created['id']}",
        json={
            "sku": new_sku,
            "name": "Updated Product",
            "unit": "kg",
            "description": "Updated description",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    body = response.json()
    assert body["sku"] == new_sku
    assert body["name"] == "Updated Product"
    assert body["unit"] == "kg"
    assert body["description"] == "Updated description"


def test_patch_category_and_location(
    client, admin_headers, product_references, db_session
):
    created = create_product(
        client, admin_headers, product_references
    )

    category_id = product_references["category_b"].id
    location_id = product_references["location_b"].id

    response = client.patch(
        f"/products/{created['id']}",
        json={
            "category_id": category_id,
            "location_id": location_id,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["category_id"] == category_id
    assert response.json()["location_id"] == location_id

    db_session.expire_all()
    stored = db_session.get(Product, created["id"])
    assert stored.category_id == category_id
    assert stored.location_id == location_id


def test_patch_description_to_null(
    client, admin_headers, product_references
):
    created = create_product(
        client, admin_headers, product_references
    )

    response = client.patch(
        f"/products/{created['id']}",
        json={"description": None},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["description"] is None


def test_empty_patch_preserves_product(
    client, admin_headers, product_references
):
    created = create_product(
        client, admin_headers, product_references
    )

    response = client.patch(
        f"/products/{created['id']}",
        json={},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == created


def test_patch_missing_product_returns_404(
    client, admin_headers
):
    response = client.patch(
        "/products/2147483647",
        json={"name": "Missing"},
        headers=admin_headers,
    )

    assert response.status_code == 404


# ============================================================
# DELETE
# ============================================================


def test_delete_product_removes_record(
    client, admin_headers, product_references, db_session
):
    created = create_product(
        client, admin_headers, product_references
    )
    product_id = created["id"]

    response = client.delete(
        f"/products/{product_id}",
        headers=admin_headers,
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    db_session.expire_all()
    assert db_session.get(Product, product_id) is None

    get_response = client.get(
        f"/products/{product_id}",
        headers=admin_headers,
    )
    assert get_response.status_code == 404


def test_delete_missing_product_returns_404(
    client, admin_headers
):
    response = client.delete(
        "/products/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


# ============================================================
# VALIDATION
# ============================================================


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sku", ""),
        ("sku", "   "),
        ("name", ""),
        ("name", "   "),
        ("unit", ""),
        ("category_id", 0),
        ("location_id", -1),
    ],
)
def test_create_rejects_invalid_fields(
    client, admin_headers, product_references, field, value
):
    payload = make_payload(product_references)
    payload[field] = value

    response = client.post(
        "/products",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field",
    ["sku", "name", "unit", "category_id", "location_id"],
)
def test_patch_rejects_null_required_fields(
    client, admin_headers, product_references, field
):
    created = create_product(
        client, admin_headers, product_references
    )

    response = client.patch(
        f"/products/{created['id']}",
        json={field: None},
        headers=admin_headers,
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "method",
    ["post", "patch"],
)
def test_quantity_cannot_be_modified_directly(
    client, admin_headers, product_references, method
):
    if method == "post":
        payload = make_payload(
            product_references,
            quantity="100.000",
        )
        response = client.post(
            "/products",
            json=payload,
            headers=admin_headers,
        )
    else:
        created = create_product(
            client, admin_headers, product_references
        )
        response = client.patch(
            f"/products/{created['id']}",
            json={"quantity": "100.000"},
            headers=admin_headers,
        )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "method",
    ["post", "patch"],
)
def test_unknown_fields_are_rejected(
    client, admin_headers, product_references, method
):
    if method == "post":
        response = client.post(
            "/products",
            json=make_payload(
                product_references,
                unknown_field="invalid",
            ),
            headers=admin_headers,
        )
    else:
        created = create_product(
            client, admin_headers, product_references
        )
        response = client.patch(
            f"/products/{created['id']}",
            json={"unknown_field": "invalid"},
            headers=admin_headers,
        )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "product_id",
    ["0", "-1", "abc"],
)
def test_invalid_product_id_returns_422(
    client, admin_headers, product_id
):
    response = client.get(
        f"/products/{product_id}",
        headers=admin_headers,
    )

    assert response.status_code == 422
