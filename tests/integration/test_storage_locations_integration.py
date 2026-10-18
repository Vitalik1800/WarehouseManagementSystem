from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.category import Category
from backend.app.models.product import Product
from backend.app.models.storage_location import StorageLocation
from backend.app.models.user import User


BASE_URL = "/storage-locations"


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
        name="Storage Administrator",
        username=f"loc_admin_{uuid4().hex[:12]}",
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
        name="Storage Worker",
        username=f"loc_worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add(worker)
    db_session.flush()

    token = create_access_token(user_id=worker.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def location(db_session, main_warehouse_id):
    location = StorageLocation(
        name=f"Location_{uuid4().hex[:12]}",
        description="Test storage location",
     warehouse_id=main_warehouse_id,)

    db_session.add(location)
    db_session.flush()

    return location


def test_list_locations_admin_success(
    client, location, admin_headers
):
    response = client.get(
        BASE_URL,
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert any(
        item["id"] == location.id
        for item in response.json()
    )


def test_list_locations_worker_success(
    client, location, worker_headers
):
    response = client.get(
        BASE_URL,
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text
    assert any(
        item["id"] == location.id
        for item in response.json()
    )


def test_list_locations_missing_token(client):
    response = client.get(BASE_URL)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "role",
    ["admin", "worker"],
)
def test_get_location_success(
    client, location, role, admin_headers, worker_headers
):
    headers = (
        admin_headers if role == "admin" else worker_headers
    )

    response = client.get(
        f"{BASE_URL}/{location.id}",
        headers=headers,
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "id": location.id,
        "name": location.name,
        "description": location.description,
        "warehouse_id": location.warehouse_id,
    }


def test_get_location_not_found(client, admin_headers):
    response = client.get(
        f"{BASE_URL}/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_get_location_missing_token(client):
    response = client.get(f"{BASE_URL}/1")

    assert response.status_code == 401


def test_create_location_admin_success(
    client, db_session, admin_headers
):
    name = f"NewLocation_{uuid4().hex[:12]}"

    response = client.post(
        BASE_URL,
        json={
            "name": name,
            "description": "New warehouse area",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert isinstance(data["id"], int)
    assert data["name"] == name
    assert data["description"] == "New warehouse area"

    db_session.expire_all()

    saved = db_session.get(StorageLocation, data["id"])

    assert saved is not None
    assert saved.name == name


def test_create_location_name_trimmed(
    client, admin_headers
):
    name = f"Trimmed_{uuid4().hex[:12]}"

    response = client.post(
        BASE_URL,
        json={"name": f"  {name}  "},
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == name


def test_create_location_duplicate_name(
    client, db_session, location, admin_headers
):
    response = client.post(
        BASE_URL,
        json={"name": location.name},
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text

    db_session.refresh(location)
    assert location.description == "Test storage location"


def test_create_location_worker_forbidden(
    client, db_session, worker_headers
):
    name = f"Forbidden_{uuid4().hex[:12]}"

    response = client.post(
        BASE_URL,
        json={"name": name},
        headers=worker_headers,
    )

    assert response.status_code == 403
    assert db_session.query(StorageLocation).filter_by(
        name=name
    ).first() is None


def test_create_location_missing_token(client):
    response = client.post(
        BASE_URL,
        json={"name": "Unauthorized location"},
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
        {"name": 123},
        {"name": "Valid", "unknown_field": "value"},
    ],
)
def test_create_location_invalid_payload(
    client, admin_headers, payload
):
    response = client.post(
        BASE_URL,
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


def test_update_location_admin_success(
    client, db_session, location, admin_headers
):
    location_id = location.id
    new_name = f"Updated_{uuid4().hex[:12]}"

    response = client.patch(
        f"{BASE_URL}/{location_id}",
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

    saved = db_session.get(StorageLocation, location_id)

    assert saved.name == new_name
    assert saved.description == "Updated description"


def test_update_location_partial_description(
    client, location, admin_headers
):
    original_name = location.name

    response = client.patch(
        f"{BASE_URL}/{location.id}",
        json={"description": "After"},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == original_name
    assert response.json()["description"] == "After"


def test_update_location_clear_description(
    client, location, admin_headers
):
    response = client.patch(
        f"{BASE_URL}/{location.id}",
        json={"description": None},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["description"] is None


def test_update_location_duplicate_name(
    client, db_session, location, admin_headers, main_warehouse_id
):
    other = StorageLocation(
        name=f"Other_{uuid4().hex[:12]}"
    , warehouse_id=main_warehouse_id)

    db_session.add(other)
    db_session.flush()

    original_name = location.name

    response = client.patch(
        f"{BASE_URL}/{location.id}",
        json={"name": other.name},
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text

    db_session.refresh(location)
    assert location.name == original_name


def test_update_location_same_name(
    client, location, admin_headers
):
    response = client.patch(
        f"{BASE_URL}/{location.id}",
        json={"name": location.name},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == location.name


def test_update_location_not_found(
    client, admin_headers
):
    response = client.patch(
        f"{BASE_URL}/2147483647",
        json={"name": "Updated"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_location_worker_forbidden(
    client, db_session, location, worker_headers
):
    original_name = location.name

    response = client.patch(
        f"{BASE_URL}/{location.id}",
        json={"name": "Unauthorized Update"},
        headers=worker_headers,
    )

    assert response.status_code == 403

    db_session.refresh(location)
    assert location.name == original_name


def test_update_location_missing_token(client):
    response = client.patch(
        f"{BASE_URL}/1",
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
        {"name": 123},
        {"unknown_field": "value"},
    ],
)
def test_update_location_invalid_payload(
    client, location, admin_headers, payload
):
    response = client.patch(
        f"{BASE_URL}/{location.id}",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


def test_update_location_empty_payload(
    client, location, admin_headers
):
    response = client.patch(
        f"{BASE_URL}/{location.id}",
        json={},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == location.name
    assert response.json()["description"] == location.description


def test_delete_location_admin_success(
    client, db_session, location, admin_headers
):
    location_id = location.id

    response = client.delete(
        f"{BASE_URL}/{location_id}",
        headers=admin_headers,
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    db_session.expire_all()

    assert db_session.get(StorageLocation, location_id) is None


def test_delete_location_not_found(
    client, admin_headers
):
    response = client.delete(
        f"{BASE_URL}/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_delete_location_worker_forbidden(
    client, db_session, location, worker_headers
):
    location_id = location.id

    response = client.delete(
        f"{BASE_URL}/{location_id}",
        headers=worker_headers,
    )

    assert response.status_code == 403

    db_session.expire_all()
    assert db_session.get(StorageLocation, location_id) is not None


def test_delete_location_missing_token(client):
    response = client.delete(f"{BASE_URL}/1")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_delete_location_with_products_conflict(
    client, db_session, location, admin_headers
):
    suffix = uuid4().hex[:12]

    category = Category(
        name=f"Category_{suffix}",
    )

    db_session.add(category)
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

    location_id = location.id
    product_id = product.id

    response = client.delete(
        f"{BASE_URL}/{location_id}",
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text

    db_session.expire_all()

    saved_location = db_session.get(
        StorageLocation, location_id
    )
    saved_product = db_session.get(Product, product_id)

    assert saved_location is not None
    assert saved_product is not None
    assert saved_product.location_id == location_id


def test_list_locations_pagination(
    client, db_session, admin_headers, main_warehouse_id
):
    suffix = uuid4().hex[:12]

    locations = [
        StorageLocation(name=f"Pagination_{suffix}_{index}", warehouse_id=main_warehouse_id)
        for index in range(3)
    ]

    db_session.add_all(locations)
    db_session.flush()

    response = client.get(
        BASE_URL,
        params={"offset": 0, "limit": 2},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2


def test_list_locations_large_offset(
    client, admin_headers
):
    response = client.get(
        BASE_URL,
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
def test_list_locations_invalid_pagination(
    client, admin_headers, params
):
    response = client.get(
        BASE_URL,
        params=params,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


@pytest.mark.parametrize("limit", [1, 100])
def test_list_locations_valid_limits(
    client, admin_headers, limit
):
    response = client.get(
        BASE_URL,
        params={"offset": 0, "limit": limit},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) <= limit


# ============================================================
# ADDITIONAL STORAGE LOCATION INTEGRATION TESTS
# ============================================================


def test_update_location_name_trimmed(
    client,
    db_session,
    location,
    admin_headers,
):
    location_id = location.id
    new_name = f"TrimmedUpdate_{uuid4().hex[:12]}"

    response = client.patch(
        f"{BASE_URL}/{location_id}",
        json={
            "name": f"   {new_name}   ",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == new_name

    db_session.expire_all()

    saved = db_session.get(
        StorageLocation,
        location_id,
    )

    assert saved is not None
    assert saved.name == new_name


def test_list_locations_nonzero_offset(
    client,
    db_session,
    admin_headers, main_warehouse_id,
):
    suffix = uuid4().hex[:12]

    locations = [
        StorageLocation(
            name=f"OffsetLocation_{suffix}_{index}"
        , warehouse_id=main_warehouse_id)
        for index in range(3)
    ]

    db_session.add_all(locations)
    db_session.flush()

    all_response = client.get(
        BASE_URL,
        params={
            "offset": 0,
            "limit": 100,
        },
        headers=admin_headers,
    )

    assert all_response.status_code == 200, all_response.text

    all_items = all_response.json()

    offset = max(0, len(all_items) - 2)

    response = client.get(
        BASE_URL,
        params={
            "offset": offset,
            "limit": 2,
        },
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


def test_list_locations_ordered_by_id(
    client,
    db_session,
    admin_headers, main_warehouse_id,
):
    suffix = uuid4().hex[:12]

    locations = [
        StorageLocation(
            name=f"OrderedLocation_{suffix}_{index}"
        , warehouse_id=main_warehouse_id)
        for index in range(3)
    ]

    db_session.add_all(locations)
    db_session.flush()

    response = client.get(
        BASE_URL,
        params={"limit": 100},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    ids = [
        item["id"]
        for item in response.json()
    ]

    assert ids == sorted(ids)


def test_create_location_minimal_payload(
    client,
    db_session,
    admin_headers,
):
    name = f"MinimalLocation_{uuid4().hex[:12]}"

    response = client.post(
        BASE_URL,
        json={
            "name": name,
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["name"] == name
    assert data["description"] is None

    db_session.expire_all()

    saved = db_session.get(
        StorageLocation,
        data["id"],
    )

    assert saved is not None
    assert saved.name == name
    assert saved.description is None


def test_create_location_explicit_null_description(
    client,
    db_session,
    admin_headers,
):
    name = f"NullDescription_{uuid4().hex[:12]}"

    response = client.post(
        BASE_URL,
        json={
            "name": name,
            "description": None,
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["name"] == name
    assert data["description"] is None

    db_session.expire_all()

    saved = db_session.get(
        StorageLocation,
        data["id"],
    )

    assert saved is not None
    assert saved.name == name
    assert saved.description is None
