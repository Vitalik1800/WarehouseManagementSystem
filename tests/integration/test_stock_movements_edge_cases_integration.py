from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import (
    Category,
    Product,
    StockMovement,
    StorageLocation,
    Supplier,
    User
)


@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session

    original = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original)


@pytest.fixture
def inventory_context(db_session):
    suffix = uuid4().hex[:12]

    category = Category(name=f"EdgeCategory_{suffix}")
    location = StorageLocation(name=f"EdgeLocation_{suffix}")
    user = User(
        name="Edge Case Worker",
        username=f"edge_{suffix}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add_all([category, location, user])
    db_session.flush()

    product = Product(
        sku=f"EDGE-{suffix}",
        name="Edge Case Product",
        unit="pcs",
        category_id=category.id,
        location_id=location.id,
        quantity=Decimal("0.000"),
    )

    db_session.add(product)
    db_session.flush()

    return {
        "product_id": product.id,
        "headers": {
            "Authorization": (
                f"Bearer {create_access_token(user_id=user.id)}"
            )
        },
    }


def create_movement(
    client,
    context,
    movement_type,
    quantity,
    *,
    supplier_id=None,
    note=None,
):
    paths = {
        "receipt": "/stock-movements/receipts",
        "issue": "/stock-movements/issues",
        "writeoff": "/stock-movements/writeoffs",
    }

    payload = {
        "product_id": context["product_id"],
        "movement_type": movement_type,
        "quantity": str(quantity),
    }

    if supplier_id is not None:
        payload["supplier_id"] = supplier_id

    if note is not None:
        payload["note"] = note

    return client.post(
        paths[movement_type],
        json=payload,
        headers=context["headers"],
    )


def stored_state(db_session, product_id):
    db_session.expire_all()

    product = db_session.get(Product, product_id)
    assert product is not None

    movements = list(
        db_session.scalars(
            select(StockMovement)
            .where(StockMovement.product_id == product_id)
            .order_by(StockMovement.id)
        ).all()
    )

    return product.quantity, movements


def test_issue_exact_remaining_stock(
    client, inventory_context, db_session
):
    context = inventory_context

    receipt = create_movement(
        client, context, "receipt", "12.500"
    )
    assert receipt.status_code == 201, receipt.text

    issue = create_movement(
        client, context, "issue", "12.500"
    )
    assert issue.status_code == 201, issue.text

    quantity, movements = stored_state(
        db_session, context["product_id"]
    )

    assert quantity == Decimal("0.000")
    assert len(movements) == 2
    assert [m.movement_type for m in movements] == [
        "receipt", "issue"
    ]

    balance = client.get(
        f"/stock-movements/products/{context['product_id']}/balance",
        headers=context["headers"],
    )

    assert balance.status_code == 200, balance.text
    assert Decimal(balance.json()["quantity"]) == Decimal("0.000")


def test_decimal_precision_across_movements(
    client, inventory_context, db_session
):
    context = inventory_context

    operations = [
        ("receipt", "0.101"),
        ("receipt", "0.202"),
        ("issue", "0.103"),
        ("writeoff", "0.099"),
    ]

    for movement_type, quantity in operations:
        response = create_movement(
            client,
            context,
            movement_type,
            quantity,
            note="Precision test" if movement_type == "writeoff" else None,
        )
        assert response.status_code == 201, response.text

    quantity, movements = stored_state(
        db_session, context["product_id"]
    )

    assert quantity == Decimal("0.101")
    assert len(movements) == 4

    calculated = sum(
        (
            m.quantity
            if m.movement_type == "receipt"
            else -m.quantity
            for m in movements
        ),
        Decimal("0.000"),
    )

    assert calculated == quantity


def test_receipt_persists_supplier_reference(
    client, inventory_context, db_session
):
    context = inventory_context

    supplier = Supplier(
        name=f"EdgeSupplier_{uuid4().hex[:12]}"
    )
    db_session.add(supplier)
    db_session.flush()

    response = create_movement(
        client,
        context,
        "receipt",
        "7.125",
        supplier_id=supplier.id,
    )

    assert response.status_code == 201, response.text
    assert response.json()["supplier_id"] == supplier.id

    quantity, movements = stored_state(
        db_session, context["product_id"]
    )

    assert quantity == Decimal("7.125")
    assert len(movements) == 1
    assert movements[0].supplier_id == supplier.id


def test_invalid_supplier_preserves_stock_and_journal(
    client, inventory_context, db_session
):
    context = inventory_context

    before_quantity, before_movements = stored_state(
        db_session, context["product_id"]
    )

    response = create_movement(
        client,
        context,
        "receipt",
        "5.000",
        supplier_id=2147483647,
    )

    assert response.status_code == 404, response.text

    after_quantity, after_movements = stored_state(
        db_session, context["product_id"]
    )

    assert after_quantity == before_quantity
    assert len(after_movements) == len(before_movements)
