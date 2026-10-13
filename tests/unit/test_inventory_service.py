from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models.product import Product
from backend.app.models.stock_movement import StockMovement
from backend.app.schemas.stock_movements import StockMovementCreate
from backend.app.services.inventory_service import (
    InventoryService,
    InsufficientStockError,
    StockMovementNotFoundError,
    StockProductNotFoundError,
    StockQuantityOverflowError,
    StockSupplierNotFoundError
)


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def service(db):
    instance = InventoryService(db)

    instance.movements.increase_stock = MagicMock()
    instance.movements.decrease_stock = MagicMock()
    instance.movements.create = MagicMock()

    return instance


@pytest.fixture
def product():
    return Product(
        id=1,
        sku="SKU-001",
        name="Test product",
        unit="pcs",
        quantity=Decimal("20.000"),
        category_id=1,
        location_id=1,
    )


def movement_data(
        movement_type="receipt",
        quantity="5.000",
        **overrides,
):
    payload = {
        "product_id": 1,
        "movement_type": movement_type,
        "quantity": quantity,
    }

    if movement_type == "writeoff":
        payload["note"] = "Damaged goods"

    payload.update(overrides)

    return StockMovementCreate.model_validate(payload)


def mock_created_movement(service):
    movement = StockMovement(
        id=10,
        product_id=1,
        user_id=7,
        movement_type="receipt",
        quantity=Decimal("5.000"),
    )

    service.movements.create = MagicMock(return_value=movement)
    return movement


def test_receipt_success(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.increase_stock = MagicMock(return_value=True)
    movement = mock_created_movement(service)

    result = service.create_movement(
        movement_data("receipt"),
        user_id=7,
    )

    assert result is movement

    service.movements.increase_stock.assert_called_once_with(
        1, Decimal("5.000")
    )
    service.movements.decrease_stock.assert_not_called()

    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(movement)
    db.rollback.assert_not_called()


def test_receipt_with_supplier(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.suppliers.get_by_id = MagicMock(return_value=object())
    service.movements.increase_stock = MagicMock(return_value=True)
    mock_created_movement(service)

    service.create_movement(
        movement_data("receipt", supplier_id=3),
        user_id=7,
    )

    service.suppliers.get_by_id.assert_called_once_with(3)

    assert service.movements.create.call_args.kwargs["supplier_id"] == 3
    db.commit.assert_called_once()


def test_issue_success(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.decrease_stock = MagicMock(return_value=True)
    mock_created_movement(service)

    service.create_movement(
        movement_data("issue", "3.000"),
        user_id=7,
    )

    service.movements.decrease_stock.assert_called_once_with(
        1, Decimal("3.000")
    )
    service.movements.increase_stock.assert_not_called()
    db.commit.assert_called_once()


def test_writeoff_success(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.decrease_stock = MagicMock(return_value=True)
    mock_created_movement(service)

    service.create_movement(
        movement_data("writeoff", "2.000"),
        user_id=7,
    )

    kwargs = service.movements.create.call_args.kwargs

    assert kwargs["movement_type"] == "writeoff"
    assert kwargs["note"] == "Damaged goods"
    db.commit.assert_called_once()


def test_user_id_is_passed_from_service(service, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.increase_stock = MagicMock(return_value=True)
    mock_created_movement(service)

    service.create_movement(
        movement_data("receipt"),
        user_id=42,
    )

    assert service.movements.create.call_args.kwargs["user_id"] == 42


def test_missing_product(service, db):
    service.movements.get_product = MagicMock(return_value=None)

    with pytest.raises(StockProductNotFoundError):
        service.create_movement(
            movement_data("receipt"),
            user_id=7,
        )

    db.commit.assert_not_called()


def test_missing_supplier(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.suppliers.get_by_id = MagicMock(return_value=None)

    with pytest.raises(StockSupplierNotFoundError):
        service.create_movement(
            movement_data("receipt", supplier_id=3),
            user_id=7,
        )

    db.commit.assert_not_called()


@pytest.mark.parametrize("movement_type", ["issue", "writeoff"])
def test_insufficient_stock(service, db, product, movement_type):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.decrease_stock = MagicMock(return_value=False)

    with pytest.raises(InsufficientStockError):
        service.create_movement(
            movement_data(movement_type, "100.000"),
            user_id=7,
        )

    service.movements.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_receipt_overflow(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.increase_stock = MagicMock(return_value=False)

    with pytest.raises(StockQuantityOverflowError):
        service.create_movement(
            movement_data("receipt"),
            user_id=7,
        )

    service.movements.create.assert_not_called()
    db.commit.assert_not_called()
    db.rollback.assert_called_once()


def test_product_disappears_during_update(service, db, product):
    service.movements.get_product = MagicMock(
        side_effect=[product, None]
    )
    service.movements.decrease_stock = MagicMock(return_value=False)

    with pytest.raises(StockProductNotFoundError):
        service.create_movement(
            movement_data("issue"),
            user_id=7,
        )

    db.rollback.assert_called_once()


def test_movement_creation_failure_rolls_back(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.increase_stock = MagicMock(return_value=True)
    service.movements.create = MagicMock(
        side_effect=RuntimeError("Database failure")
    )

    with pytest.raises(RuntimeError):
        service.create_movement(
            movement_data("receipt"),
            user_id=7,
        )

    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_commit_failure_rolls_back(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.increase_stock = MagicMock(return_value=True)
    mock_created_movement(service)
    db.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError):
        service.create_movement(
            movement_data("receipt"),
            user_id=7,
        )

    db.rollback.assert_called_once()


def test_integrity_error_rolls_back(service, db, product):
    service.movements.get_product = MagicMock(return_value=product)
    service.movements.increase_stock = MagicMock(return_value=True)

    error = IntegrityError(
        "INSERT",
        {},
        Exception(9999, "Integrity failure"),
    )

    service.movements.create = MagicMock(side_effect=error)

    with pytest.raises(IntegrityError):
        service.create_movement(
            movement_data("receipt"),
            user_id=7,
        )

    db.rollback.assert_called_once()


def test_get_movement_success(service):
    movement = StockMovement(id=5)
    service.movements.get_by_id = MagicMock(return_value=movement)

    assert service.get_movement(5) is movement


def test_get_movement_not_found(service):
    service.movements.get_by_id = MagicMock(return_value=None)

    with pytest.raises(StockMovementNotFoundError):
        service.get_movement(999)


def test_list_movements_forwards_filters(service):
    service.movements.get_all = MagicMock(return_value=[])

    result = service.list_movements(
        offset=5,
        limit=10,
        product_id=1,
        user_id=2,
        supplier_id=3,
        movement_type="receipt",
    )

    assert result == []

    service.movements.get_all.assert_called_once_with(
        offset=5,
        limit=10,
        product_id=1,
        user_id=2,
        supplier_id=3,
        movement_type="receipt",
    )


def test_get_stock_balance(service, product):
    service.movements.get_product = MagicMock(return_value=product)

    balance = service.get_stock_balance(1)

    assert balance.product_id == 1
    assert balance.sku == "SKU-001"
    assert balance.name == "Test product"
    assert balance.unit == "pcs"
    assert balance.quantity == Decimal("20.000")


def test_get_stock_balance_missing_product(service):
    service.movements.get_product = MagicMock(return_value=None)

    with pytest.raises(StockProductNotFoundError):
        service.get_stock_balance(999)
