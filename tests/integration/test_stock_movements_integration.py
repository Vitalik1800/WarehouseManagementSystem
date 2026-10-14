from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.security import create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models import (
    Category,
    Product,
    StockMovement,
    StorageLocation,
    User,
)
from backend.app.schemas.stock_movements import StockMovementCreate
from backend.app.services.inventory_service import InventoryService


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
def worker_headers(db_session):
    user = User(
        name="Inventory Integration Worker",
        username=f"inventory_{uuid4().hex[:12]}",
        password_hash="test_hash",
        role="worker",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    token = create_access_token(user_id=user.id)

    return {
        "Authorization": f"Bearer {token}"
    }


@pytest.fixture
def product(db_session):
    suffix = uuid4().hex[:12]

    category = Category(
        name=f"InventoryCategory_{suffix}"
    )

    location = StorageLocation(
        name=f"InventoryLocation_{suffix}"
    )

    db_session.add_all([category, location])
    db_session.flush()

    product = Product(
        sku=f"INV-{suffix}",
        name="Inventory Integration Product",
        unit="pcs",
        category_id=category.id,
        location_id=location.id,
        quantity=Decimal("0.000"),
    )

    db_session.add(product)
    db_session.flush()

    return product


def create_movement(
        client,
        headers,
        product_id,
        movement_type,
        quantity,
        note=None,
):
    paths = {
        "receipt": "/stock-movements/receipts",
        "issue": "/stock-movements/issues",
        "writeoff": "/stock-movements/writeoffs",
    }

    payload = {
        "product_id": product_id,
        "movement_type": movement_type,
        "quantity": str(quantity),
    }

    if note is not None:
        payload["note"] = note

    return client.post(
        paths[movement_type],
        json=payload,
        headers=headers,
    )


def get_balance(client, headers, product_id):
    return client.get(
        f"/stock-movements/products/{product_id}/balance",
        headers=headers,
    )


def get_stored_quantity(db_session, product_id):
    db_session.expire_all()

    stored = db_session.get(Product, product_id)

    assert stored is not None

    return stored.quantity


def get_stored_movements(db_session, product_id):
    db_session.expire_all()

    statement = (
        select(StockMovement)
        .where(StockMovement.product_id == product_id)
        .order_by(StockMovement.id.asc())
    )

    return list(
        db_session.scalars(statement).all()
    )


def test_receipt_issue_writeoff_balance_and_journal(
        client,
        worker_headers,
        product,
        db_session,
):
    product_id = product.id

    operations = [
        ("receipt", "100.000", None),
        ("issue", "30.000", None),
        ("writeoff", "5.000", "Damaged goods"),
    ]

    expected_balances = [
        Decimal("100.000"),
        Decimal("70.000"),
        Decimal("65.000"),
    ]

    movement_ids = []

    for operation, expected in zip(
            operations,
            expected_balances,
    ):
        movement_type, quantity, note = operation

        response = create_movement(
            client,
            worker_headers,
            product_id,
            movement_type,
            quantity,
            note,
        )

        assert response.status_code == 201, response.text

        body = response.json()

        assert body["product_id"] == product_id
        assert body["movement_type"] == movement_type
        assert Decimal(body["quantity"]) == Decimal(quantity)

        movement_ids.append(body["id"])

        balance_response = get_balance(
            client,
            worker_headers,
            product_id,
        )

        assert balance_response.status_code == 200
        assert Decimal(
            balance_response.json()["quantity"]
        ) == expected

        assert get_stored_quantity(
            db_session,
            product_id,
        ) == expected

    movements = get_stored_movements(
        db_session,
        product_id,
    )

    assert len(movements) == 3

    assert [movement.id for movement in movements] == (
        movement_ids
    )

    assert [
               movement.movement_type
               for movement in movements
           ] == [
               "receipt",
               "issue",
               "writeoff",
           ]

    receipts = sum(
        (
            movement.quantity
            for movement in movements
            if movement.movement_type == "receipt"
        ),
        Decimal("0"),
    )

    issues = sum(
        (
            movement.quantity
            for movement in movements
            if movement.movement_type == "issue"
        ),
        Decimal("0"),
    )

    writeoffs = sum(
        (
            movement.quantity
            for movement in movements
            if movement.movement_type == "writeoff"
        ),
        Decimal("0"),
    )

    calculated_balance = receipts - issues - writeoffs

    assert calculated_balance == Decimal("65.000")
    assert calculated_balance == get_stored_quantity(
        db_session,
        product_id,
    )

    journal_response = client.get(
        "/stock-movements",
        params={"product_id": product_id},
        headers=worker_headers,
    )

    assert journal_response.status_code == 200

    journal = journal_response.json()

    assert len(journal) == 3
    assert {entry["id"] for entry in journal} == set(
        movement_ids
    )


def test_insufficient_stock_preserves_balance_and_journal(
        client,
        worker_headers,
        product,
        db_session,
):
    product_id = product.id

    receipt = create_movement(
        client,
        worker_headers,
        product_id,
        "receipt",
        "10.000",
    )

    assert receipt.status_code == 201, receipt.text

    before_quantity = get_stored_quantity(
        db_session,
        product_id,
    )

    before_movements = get_stored_movements(
        db_session,
        product_id,
    )

    response = create_movement(
        client,
        worker_headers,
        product_id,
        "issue",
        "20.000",
    )

    assert response.status_code == 409, response.text

    assert get_stored_quantity(
        db_session,
        product_id,
    ) == before_quantity

    after_movements = get_stored_movements(
        db_session,
        product_id,
    )

    assert len(after_movements) == len(before_movements)


def test_stock_overflow_preserves_balance_and_journal(
        client,
        worker_headers,
        product,
        db_session,
):
    product_id = product.id

    maximum = Decimal("99999999999.999")

    receipt = create_movement(
        client,
        worker_headers,
        product_id,
        "receipt",
        maximum,
    )

    assert receipt.status_code == 201, receipt.text

    before_movements = get_stored_movements(
        db_session,
        product_id,
    )

    response = create_movement(
        client,
        worker_headers,
        product_id,
        "receipt",
        "0.001",
    )

    assert response.status_code == 409, response.text

    assert get_stored_quantity(
        db_session,
        product_id,
    ) == maximum

    after_movements = get_stored_movements(
        db_session,
        product_id,
    )

    assert len(after_movements) == len(before_movements)


def test_writeoff_requires_reason_and_preserves_stock(
    client,
     worker_headers,
    product,
        db_session,
):
    product_id = product.id

    response = create_movement(
        client,
        worker_headers,
        product_id,
        "writeoff",
        "1.000",
    )

    assert response.status_code == 422, response.text

    assert get_stored_quantity(
        db_session,
        product_id,
    ) == Decimal("0.000")

    assert get_stored_movements(
        db_session,
        product_id,
    ) == []


def test_balance_for_missing_product_returns_404(
    client,
    worker_headers,
):
    response = get_balance(
        client,
        worker_headers,
        2147483647,
    )

    assert response.status_code == 404


def test_journal_filter_returns_only_requested_product(
    client,
    worker_headers,
    product,
    db_session,
):
    first = create_movement(
        client,
        worker_headers,
        product.id,
        "receipt",
        "8.000",
    )

    assert first.status_code == 201, first.text

    second_product = Product(
        sku=f"INV-SECOND-{uuid4().hex[:12]}",
        name="Second Inventory Product",
        unit="pcs",
        category_id=product.category_id,
        location_id=product.location_id,
        quantity=Decimal("0.000"),
    )

    db_session.add(second_product)
    db_session.flush()

    second = create_movement(
        client,
        worker_headers,
        second_product.id,
        "receipt",
        "3.000",
    )

    assert second.status_code == 201, second.text

    response = client.get(
        "/stock-movements",
        params={"product_id": product.id},
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text

    journal = response.json()

    assert len(journal) == 1
    assert journal[0]["product_id"] == product.id
    assert journal[0]["id"] == first.json()["id"]


def test_failed_journal_insert_rolls_back_stock(
    db_session,
    product,
):
    from sqlalchemy.exc import IntegrityError

    from backend.app.schemas.stock_movements import (
        StockMovementCreate,
    )
    from backend.app.services.inventory_service import (
        InventoryService,
    )

    product_id = product.id

    # Finish the fixture's current SAVEPOINT.
    # The outer transaction remains active and will be
    # rolled back by db_session after the test.
    db_session.commit()

    service = InventoryService(db_session)

    initial_quantity = get_stored_quantity(
        db_session,
        product_id,
    )

    initial_movements = get_stored_movements(
        db_session,
        product_id,
    )

    assert initial_quantity == Decimal("0.000")
    assert initial_movements == []

    data = StockMovementCreate(
        product_id=product_id,
        movement_type="receipt",
        quantity=Decimal("25.000"),
    )

    invalid_user_id = 2147483647

    with pytest.raises(IntegrityError):
        service.create_movement(
            data=data,
            user_id=invalid_user_id,
        )

    # A failed journal INSERT must not leave
    # the preceding stock UPDATE in the database.
    actual_quantity = get_stored_quantity(
        db_session,
        product_id,
    )

    actual_movements = get_stored_movements(
        db_session,
        product_id,
    )

    assert actual_quantity == initial_quantity
    assert actual_movements == []


@pytest.mark.parametrize(
    "movement_type,note",
    [
        ("issue", None),
        ("writeoff", "Damaged goods"),
    ],
)
def test_failed_outgoing_journal_insert_rolls_back_stock(
        db_session,
        product,
        movement_type,
        note,
):
    product_id = product.id

    product.quantity = Decimal("100.000")
    db_session.flush()
    db_session.commit()

    service = InventoryService(db_session)

    initial_quantity = get_stored_quantity(
        db_session,
        product_id,
    )
    initial_movements = get_stored_movements(
        db_session,
        product_id,
    )

    assert initial_quantity == Decimal("100.000")
    assert initial_movements == []

    data = StockMovementCreate(
        product_id=product_id,
        movement_type=movement_type,
        quantity=Decimal("25.000"),
        note=note,
    )

    invalid_user_id = 2147483647

    with pytest.raises(IntegrityError):
        service.create_movement(
            data=data,
            user_id=invalid_user_id,
        )

    assert get_stored_quantity(
        db_session,
        product_id,
    ) == initial_quantity

    assert get_stored_movements(
        db_session,
        product_id,
    ) == initial_movements


def test_concurrent_issues_do_not_oversell(test_engine):
    suffix = uuid4().hex[:12]

    # Dedicated committed fixtures visible to both connections.
    with Session(test_engine) as session:
        category = Category(name=f"ConcurrentCategory_{suffix}")
        location = StorageLocation(
            name=f"ConcurrentLocation_{suffix}"
        )
        user = User(
            name="Concurrent Inventory Worker",
            username=f"concurrent_{suffix}",
            password_hash="test_hash",
            role="worker",
            is_active=True,
        )

        session.add_all([category, location, user])
        session.flush()

        product = Product(
            sku=f"CONCURRENT-{suffix}",
            name="Concurrent Inventory Product",
            unit="pcs",
            category_id=category.id,
            location_id=location.id,
            quantity=Decimal("100.000"),
        )

        session.add(product)
        session.flush()

        product_id = product.id
        category_id = category.id
        location_id = location.id
        user_id = user.id

        session.commit()

    barrier = Barrier(2, timeout=10)

    def issue_stock():
        with Session(test_engine) as session:
            service = InventoryService(session)

            # Both workers start their operation together.
            barrier.wait()

            try:
                service.create_movement(
                    data=StockMovementCreate(
                        product_id=product_id,
                        movement_type="issue",
                        quantity=Decimal("70.000"),
                    ),
                    user_id=user_id,
                )
                return "success"
            except Exception as exc:
                from backend.app.services.inventory_service import (
                    InsufficientStockError,
                )

                if isinstance(exc, InsufficientStockError):
                    return "insufficient"

                raise

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(issue_stock)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=20)
                for future in futures
            ]

        assert sorted(results) == [
            "insufficient",
            "success",
        ]

        with Session(test_engine) as session:
            stored_product = session.get(Product, product_id)

            assert stored_product is not None
            assert stored_product.quantity == Decimal("30.000")

            movements = list(
                session.scalars(
                    select(StockMovement).where(
                        StockMovement.product_id == product_id
                    )
                ).all()
            )

            assert len(movements) == 1
            assert movements[0].movement_type == "issue"
            assert movements[0].quantity == Decimal("70.000")
            assert movements[0].user_id == user_id

    finally:
        # Cleanup is independent of the test assertions.
        with Session(test_engine) as session:
            session.execute(
                delete(StockMovement).where(
                    StockMovement.product_id == product_id
                )
            )
            session.execute(
                delete(Product).where(Product.id == product_id)
            )
            session.execute(
                delete(User).where(User.id == user_id)
            )
            session.execute(
                delete(Category).where(Category.id == category_id)
            )
            session.execute(
                delete(StorageLocation).where(
                    StorageLocation.id == location_id
                )
            )
            session.commit()


def test_concurrent_receipts_do_not_overflow(test_engine):
    from backend.app.services.inventory_service import (
        StockQuantityOverflowError,
    )

    suffix = uuid4().hex[:12]
    maximum = Decimal("99999999999.999")
    initial_quantity = maximum - Decimal("10.000")

    with Session(test_engine) as session:
        category = Category(
            name=f"ReceiptCategory_{suffix}"
        )
        location = StorageLocation(
            name=f"ReceiptLocation_{suffix}"
        )
        user = User(
            name="Concurrent Receipt Worker",
            username=f"receipt_{suffix}",
            password_hash="test_hash",
            role="worker",
            is_active=True,
        )

        session.add_all([category, location, user])
        session.flush()

        product = Product(
            sku=f"RECEIPT-{suffix}",
            name="Concurrent Receipt Product",
            unit="pcs",
            category_id=category.id,
            location_id=location.id,
            quantity=initial_quantity,
        )

        session.add(product)
        session.flush()

        product_id = product.id
        category_id = category.id
        location_id = location.id
        user_id = user.id

        session.commit()

    barrier = Barrier(2, timeout=10)

    def receive_stock():
        with Session(test_engine) as session:
            service = InventoryService(session)

            barrier.wait()

            try:
                service.create_movement(
                    data=StockMovementCreate(
                        product_id=product_id,
                        movement_type="receipt",
                        quantity=Decimal("7.000"),
                    ),
                    user_id=user_id,
                )
                return "success"

            except StockQuantityOverflowError:
                return "overflow"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(receive_stock)
                for _ in range(2)
            ]

            results = [
                future.result(timeout=20)
                for future in futures
            ]

        assert sorted(results) == [
            "overflow",
            "success",
        ]

        with Session(test_engine) as session:
            stored_product = session.get(
                Product,
                product_id,
            )

            assert stored_product is not None
            assert stored_product.quantity == (
                    initial_quantity + Decimal("7.000")
            )

            movements = list(
                session.scalars(
                    select(StockMovement).where(
                        StockMovement.product_id == product_id
                    )
                ).all()
            )

            assert len(movements) == 1
            assert movements[0].movement_type == "receipt"
            assert movements[0].quantity == Decimal("7.000")
            assert movements[0].user_id == user_id

    finally:
        with Session(test_engine) as session:
            session.execute(
                delete(StockMovement).where(
                    StockMovement.product_id == product_id
                )
            )
            session.execute(
                delete(Product).where(
                    Product.id == product_id
                )
            )
            session.execute(
                delete(User).where(
                    User.id == user_id
                )
            )
            session.execute(
                delete(Category).where(
                    Category.id == category_id
                )
            )
            session.execute(
                delete(StorageLocation).where(
                    StorageLocation.id == location_id
                )
            )
            session.commit()


# ============================================================
# Stage 8.3 - Stock Movement Journal Integration Tests
# ============================================================


@pytest.fixture
def journal_movements(client, worker_headers, product, db_session):
    from datetime import datetime

    operations = [
        ("receipt", "100.000", datetime(2026, 10, 1, 9, 0)),
        ("issue", "10.000", datetime(2026, 10, 5, 12, 0)),
        ("writeoff", "5.000", datetime(2026, 10, 5, 12, 0)),
        ("receipt", "20.000", datetime(2026, 10, 10, 15, 0)),
    ]

    movements = []

    for movement_type, quantity, created_at in operations:
        response = create_movement(
            client,
            worker_headers,
            product.id,
            movement_type,
            quantity,
            note=(
                "Damaged goods"
                if movement_type == "writeoff"
                else None
            ),
        )

        assert response.status_code == 201, response.text

        movement_id = response.json()["id"]
        movement = db_session.get(StockMovement, movement_id)

        assert movement is not None

        movement.created_at = created_at
        movements.append(movement)

    db_session.flush()

    return {
        "product_id": product.id,
        "ids": [movement.id for movement in movements],
    }


@pytest.mark.parametrize(
    "params,expected_indices",
    [
        (
                {"date_from": "2026-10-05T12:00:00"},
                [3, 2, 1],
        ),
        (
                {"date_to": "2026-10-05T12:00:00"},
                [2, 1, 0],
        ),
        (
                {
                    "date_from": "2026-10-05T12:00:00",
                    "date_to": "2026-10-05T12:00:00",
                },
                [2, 1],
        ),
        (
                {"sort_by": "oldest"},
                [0, 1, 2, 3],
        ),
        (
                {"sort_by": "newest"},
                [3, 2, 1, 0],
        ),
        (
                {
                    "date_from": "2026-10-05T12:00:00",
                    "date_to": "2026-10-10T15:00:00",
                    "movement_type": "receipt",
                    "sort_by": "oldest",
                },
                [3],
        ),
        (
                {
                    "sort_by": "oldest",
                    "offset": 1,
                    "limit": 2,
                },
                [1, 2],
        ),
    ],
)
def test_journal_date_filters_sort_and_pagination(
        client,
        worker_headers,
        journal_movements,
        params,
        expected_indices,
):
    response = client.get(
        "/stock-movements",
        params={
            "product_id": journal_movements["product_id"],
            **params,
        },
        headers=worker_headers,
    )

    assert response.status_code == 200, response.text

    actual_ids = [
        movement["id"]
        for movement in response.json()
    ]

    expected_ids = [
        journal_movements["ids"][index]
        for index in expected_indices
    ]

    assert actual_ids == expected_ids
