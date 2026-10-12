from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.supplier import Supplier
from backend.app.models.user import User

from decimal import Decimal

from backend.app.models.category import Category
from backend.app.models.product import Product
from backend.app.models.stock_movement import StockMovement
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
        name="Supplier Administrator",
        username=f"sup_admin_{uuid4().hex[:12]}",
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
        name="Supplier Worker",
        username=f"sup_worker_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add(worker)
    db_session.flush()

    token = create_access_token(user_id=worker.id)

    return {"Authorization": f"Bearer {token}"}


def test_list_suppliers_admin_success(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"Supplier_{uuid4().hex[:12]}",
        contact_person="John Smith",
        email="john@example.com",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.get(
        "/suppliers",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    assert any(
        item["id"] == supplier.id
        and item["name"] == supplier.name
        for item in response.json()
    )


def test_list_suppliers_worker_success(
        client,
        db_session,
        worker_headers,
):
    supplier = Supplier(
        name=f"WorkerSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.get(
        "/suppliers",
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text

    assert any(
        item["id"] == supplier.id
        for item in response.json()
    )


def test_get_supplier_admin_success(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"DetailedSupplier_{uuid4().hex[:12]}",
        contact_person="Jane Doe",
        phone="+380671234567",
        email="jane@example.com",
        address="Kyiv, Ukraine",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.get(
        f"/suppliers/{supplier.id}",
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["id"] == supplier.id
    assert data["name"] == supplier.name
    assert data["contact_person"] == "Jane Doe"
    assert data["phone"] == "+380671234567"
    assert data["email"] == "jane@example.com"
    assert data["address"] == "Kyiv, Ukraine"


def test_get_supplier_worker_success(
        client,
        db_session,
        worker_headers,
):
    supplier = Supplier(
        name=f"ReadableSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.get(
        f"/suppliers/{supplier.id}",
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["id"] == supplier.id


def test_list_suppliers_missing_token(client):
    response = client.get("/suppliers")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_get_supplier_not_found(
        client,
        admin_headers,
):
    response = client.get(
        "/suppliers/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_supplier_admin_success(
        client,
        db_session,
        admin_headers,
):
    name = f"NewSupplier_{uuid4().hex[:12]}"

    response = client.post(
        "/suppliers",
        json={
            "name": name,
            "contact_person": "Ivan Petrenko",
            "phone": "+380671234567",
            "email": "ivan@example.com",
            "address": "Lviv, Ukraine",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert isinstance(data["id"], int)
    assert data["name"] == name
    assert data["contact_person"] == "Ivan Petrenko"
    assert data["phone"] == "+380671234567"
    assert data["email"] == "ivan@example.com"
    assert data["address"] == "Lviv, Ukraine"

    db_session.expire_all()

    saved = db_session.get(Supplier, data["id"])

    assert saved is not None
    assert saved.name == name


def test_create_supplier_duplicate_name_allowed(
        client,
        db_session,
        admin_headers,
):
    name = f"DuplicateSupplier_{uuid4().hex[:12]}"

    first = client.post(
        "/suppliers",
        json={"name": name},
        headers=admin_headers,
    )

    second = client.post(
        "/suppliers",
        json={"name": name},
        headers=admin_headers,
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text

    first_id = first.json()["id"]
    second_id = second.json()["id"]

    assert first_id != second_id

    db_session.expire_all()

    assert db_session.get(Supplier, first_id) is not None
    assert db_session.get(Supplier, second_id) is not None


def test_create_supplier_minimal_payload(
        client,
        admin_headers,
):
    name = f"MinimalSupplier_{uuid4().hex[:12]}"

    response = client.post(
        "/suppliers",
        json={"name": name},
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["name"] == name
    assert data["contact_person"] is None
    assert data["phone"] is None
    assert data["email"] is None
    assert data["address"] is None


def test_create_supplier_worker_forbidden(
        client,
        db_session,
        worker_headers,
):
    name = f"ForbiddenSupplier_{uuid4().hex[:12]}"

    response = client.post(
        "/suppliers",
        json={"name": name},
        headers=worker_headers,
    )

    assert response.status_code == 403

    assert db_session.query(Supplier).filter_by(
        name=name
    ).first() is None


def test_create_supplier_missing_token(client):
    response = client.post(
        "/suppliers",
        json={"name": "Unauthorized Supplier"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"name": "A" * 151},
        {"name": "Valid", "email": "invalid-email"},
        {"name": "Valid", "phone": "1" * 31},
        {"name": "Valid", "contact_person": "A" * 151},
        {"name": "Valid", "unknown_field": "value"},
    ],
)
def test_create_supplier_invalid_payload(
        client,
        admin_headers,
        payload,
):
    response = client.post(
        "/suppliers",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


def test_update_supplier_admin_success(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"OriginalSupplier_{uuid4().hex[:12]}",
        contact_person="Original Person",
        phone="+380671111111",
        email="original@example.com",
        address="Kyiv",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.patch(
        f"/suppliers/{supplier.id}",
        json={
            "name": "Updated Supplier",
            "contact_person": "Updated Person",
            "email": "updated@example.com",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["name"] == "Updated Supplier"
    assert data["contact_person"] == "Updated Person"
    assert data["email"] == "updated@example.com"

    # Поля, які не передавалися, повинні залишитися без змін.
    assert data["phone"] == "+380671111111"
    assert data["address"] == "Kyiv"

    db_session.expire_all()

    saved = db_session.get(Supplier, supplier.id)

    assert saved.name == "Updated Supplier"
    assert saved.email == "updated@example.com"


def test_update_supplier_clear_optional_fields(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"ClearFieldsSupplier_{uuid4().hex[:12]}",
        contact_person="Contact",
        phone="+380671234567",
        email="contact@example.com",
        address="Odesa",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.patch(
        f"/suppliers/{supplier.id}",
        json={
            "contact_person": None,
            "phone": None,
            "email": None,
            "address": None,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["name"] == supplier.name
    assert data["contact_person"] is None
    assert data["phone"] is None
    assert data["email"] is None
    assert data["address"] is None


def test_update_supplier_empty_payload(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"UnchangedSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.patch(
        f"/suppliers/{supplier.id}",
        json={},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == supplier.name


def test_update_supplier_not_found(
        client,
        admin_headers,
):
    response = client.patch(
        "/suppliers/2147483647",
        json={"name": "Unknown Supplier"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_supplier_worker_forbidden(
        client,
        db_session,
        worker_headers,
):
    supplier = Supplier(
        name=f"ProtectedSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    original_name = supplier.name

    response = client.patch(
        f"/suppliers/{supplier.id}",
        json={"name": "Forbidden Update"},
        headers=worker_headers,
    )

    assert response.status_code == 403

    db_session.refresh(supplier)

    assert supplier.name == original_name


def test_update_supplier_missing_token(
        client,
        db_session,
):
    supplier = Supplier(
        name=f"UnauthorizedSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.patch(
        f"/suppliers/{supplier.id}",
        json={"name": "Unauthorized Update"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "   "},
        {"name": None},
        {"name": "A" * 151},
        {"email": "invalid-email"},
        {"phone": "1" * 31},
        {"contact_person": "A" * 151},
        {"unknown_field": "value"},
    ],
)
def test_update_supplier_invalid_payload(
        client,
        db_session,
        admin_headers,
        payload,
):
    supplier = Supplier(
        name=f"ValidationSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.patch(
        f"/suppliers/{supplier.id}",
        json=payload,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text

    db_session.refresh(supplier)

    assert supplier.name.startswith("ValidationSupplier_")


def test_delete_supplier_admin_success(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"DeleteSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    supplier_id = supplier.id

    response = client.delete(
        f"/suppliers/{supplier_id}",
        headers=admin_headers,
    )

    assert response.status_code == 204, response.text
    assert response.content == b""

    db_session.expire_all()

    assert db_session.get(Supplier, supplier_id) is None


def test_delete_supplier_not_found(
        client,
        admin_headers,
):
    response = client.delete(
        "/suppliers/2147483647",
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_delete_supplier_worker_forbidden(
        client,
        db_session,
        worker_headers,
):
    supplier = Supplier(
        name=f"ProtectedDeleteSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.delete(
        f"/suppliers/{supplier.id}",
        headers=worker_headers,
    )

    assert response.status_code == 403

    db_session.expire_all()

    assert db_session.get(Supplier, supplier.id) is not None


def test_delete_supplier_missing_token(
        client,
        db_session,
):
    supplier = Supplier(
        name=f"UnauthorizedDeleteSupplier_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    response = client.delete(
        f"/suppliers/{supplier.id}",
    )

    assert response.status_code == 401

    db_session.expire_all()

    assert db_session.get(Supplier, supplier.id) is not None


@pytest.mark.parametrize(
    "supplier_id",
    [
        0,
        -1,
    ],
)
def test_delete_supplier_invalid_id(
        client,
        admin_headers,
        supplier_id,
):
    response = client.delete(
        f"/suppliers/{supplier_id}",
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_delete_supplier_in_use_returns_409(
        client,
        db_session,
        admin_headers,
):
    unique_id = uuid4().hex[:12]

    category = Category(
        name=f"SupplierCategory_{unique_id}",
    )

    location = StorageLocation(
        name=f"SupplierLocation_{unique_id}",
    )

    supplier = Supplier(
        name=f"SupplierInUse_{unique_id}",
    )

    db_session.add_all([
        category,
        location,
        supplier,
    ])
    db_session.flush()

    product = Product(
        sku=f"SUP-{unique_id}",
        name=f"SupplierProduct_{unique_id}",
        category_id=category.id,
        location_id=location.id,
        quantity=Decimal("10.000"),
    )

    db_session.add(product)
    db_session.flush()

    # Створюємо користувача, від імені якого
    # зареєстровано операцію руху товарів.
    movement_user = User(
        name="Stock Movement Operator",
        username=f"sup_operator_{unique_id}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add(movement_user)
    db_session.flush()

    movement = StockMovement(
        product_id=product.id,
        user_id=movement_user.id,
        supplier_id=supplier.id,
        movement_type="receipt",
        quantity=Decimal("5.000"),
        note="Supplier deletion protection test",
    )

    db_session.add(movement)
    db_session.flush()

    supplier_id = supplier.id
    movement_id = movement.id

    response = client.delete(
        f"/suppliers/{supplier_id}",
        headers=admin_headers,
    )

    assert response.status_code == 409, response.text

    assert "detail" in response.json()

    # Помилка 409 не повинна видаляти записи.
    db_session.expire_all()

    saved_supplier = db_session.get(
        Supplier,
        supplier_id,
    )

    saved_movement = db_session.get(
        StockMovement,
        movement_id,
    )

    assert saved_supplier is not None
    assert saved_movement is not None
    assert saved_movement.supplier_id == supplier_id


def test_list_suppliers_pagination(
        client,
        db_session,
        admin_headers,
):
    unique_id = uuid4().hex[:12]

    suppliers = [
        Supplier(name=f"PaginationSupplier_{unique_id}_{index}")
        for index in range(5)
    ]

    db_session.add_all(suppliers)
    db_session.flush()

    response = client.get(
        "/suppliers",
        params={
            "offset": 0,
            "limit": 2,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2

    first_page_ids = [
        item["id"] for item in response.json()
    ]

    response = client.get(
        "/suppliers",
        params={
            "offset": 2,
            "limit": 2,
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert len(response.json()) == 2

    second_page_ids = [
        item["id"] for item in response.json()
    ]

    assert set(first_page_ids).isdisjoint(second_page_ids)


def test_list_suppliers_ordered_by_id(
        client,
        db_session,
        admin_headers,
):
    unique_id = uuid4().hex[:12]

    suppliers = [
        Supplier(name=f"OrderedSupplier_{unique_id}_{index}")
        for index in range(3)
    ]

    db_session.add_all(suppliers)
    db_session.flush()

    response = client.get(
        "/suppliers",
        params={"limit": 100},
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    ids = [
        item["id"] for item in response.json()
    ]

    assert ids == sorted(ids)


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
def test_list_suppliers_invalid_pagination(
        client,
        admin_headers,
        params,
):
    response = client.get(
        "/suppliers",
        params=params,
        headers=admin_headers,
    )

    assert response.status_code == 422, response.text


# ============================================================
# ADDITIONAL SUPPLIER INTEGRATION TESTS
# ============================================================


def test_get_supplier_missing_token(client):
    response = client.get("/suppliers/1")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_create_supplier_name_trimmed(
        client,
        db_session,
        admin_headers,
):
    name = f"TrimmedSupplier_{uuid4().hex[:12]}"

    response = client.post(
        "/suppliers",
        json={
            "name": f"   {name}   ",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["name"] == name

    supplier_id = response.json()["id"]

    db_session.expire_all()

    saved = db_session.get(Supplier, supplier_id)

    assert saved is not None
    assert saved.name == name


def test_update_supplier_name_trimmed(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"BeforeTrim_{uuid4().hex[:12]}",
    )

    db_session.add(supplier)
    db_session.flush()

    supplier_id = supplier.id
    new_name = f"AfterTrim_{uuid4().hex[:12]}"

    response = client.patch(
        f"/suppliers/{supplier_id}",
        json={
            "name": f"   {new_name}   ",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text
    assert response.json()["name"] == new_name

    db_session.expire_all()

    saved = db_session.get(Supplier, supplier_id)

    assert saved is not None
    assert saved.name == new_name


def test_update_supplier_same_name_success(
        client,
        db_session,
        admin_headers,
):
    supplier = Supplier(
        name=f"SameNameSupplier_{uuid4().hex[:12]}",
        contact_person="Original Contact",
    )

    db_session.add(supplier)
    db_session.flush()

    supplier_id = supplier.id
    original_name = supplier.name

    response = client.patch(
        f"/suppliers/{supplier_id}",
        json={
            "name": original_name,
            "contact_person": "Updated Contact",
        },
        headers=admin_headers,
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["name"] == original_name
    assert data["contact_person"] == "Updated Contact"

    db_session.expire_all()

    saved = db_session.get(Supplier, supplier_id)

    assert saved is not None
    assert saved.name == original_name
    assert saved.contact_person == "Updated Contact"


def test_create_supplier_explicit_null_optional_fields(
        client,
        db_session,
        admin_headers,
):
    name = f"NullFieldsSupplier_{uuid4().hex[:12]}"

    response = client.post(
        "/suppliers",
        json={
            "name": name,
            "contact_person": None,
            "phone": None,
            "email": None,
            "address": None,
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["name"] == name
    assert data["contact_person"] is None
    assert data["phone"] is None
    assert data["email"] is None
    assert data["address"] is None

    db_session.expire_all()

    saved = db_session.get(Supplier, data["id"])

    assert saved is not None
    assert saved.contact_person is None
    assert saved.phone is None
    assert saved.email is None
    assert saved.address is None


def test_create_supplier_contact_fields_trimmed(
        client,
        db_session,
        admin_headers,
):
    name = f"TrimmedContacts_{uuid4().hex[:12]}"

    response = client.post(
        "/suppliers",
        json={
            "name": name,
            "contact_person": "   Ivan Petrenko   ",
            "phone": "   +380671234567   ",
            "email": "   ivan@example.com   ",
            "address": "   Kyiv, Ukraine   ",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text

    data = response.json()

    assert data["contact_person"] == "Ivan Petrenko"
    assert data["phone"] == "+380671234567"
    assert data["email"] == "ivan@example.com"
    assert data["address"] == "Kyiv, Ukraine"

    db_session.expire_all()

    saved = db_session.get(Supplier, data["id"])

    assert saved is not None
    assert saved.contact_person == "Ivan Petrenko"
    assert saved.phone == "+380671234567"
    assert saved.email == "ivan@example.com"
    assert saved.address == "Kyiv, Ukraine"
