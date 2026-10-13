from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.sql.dml import Update

from backend.app.models.product import Product
from backend.app.models.stock_movement import StockMovement
from backend.app.repositories.stock_movement_repository import (
    StockMovementRepository
)


@pytest.fixture
def db():
    return MagicMock()


@pytest.fixture
def repository(db):
    return StockMovementRepository(db)


def test_get_by_id(repository, db):
    movement = StockMovement(id=1)

    db.get.return_value = movement

    result = repository.get_by_id(1)

    assert result is movement
    db.get.assert_called_once_with(StockMovement, 1)


def test_get_product(repository, db):
    product = Product(id=2)

    db.get.return_value = product

    result = repository.get_product(2)

    assert result is product
    db.get.assert_called_once_with(Product, 2)


def test_get_all_default_pagination(repository, db):
    movement = StockMovement(id=1)

    db.scalars.return_value.all.return_value = [movement]

    result = repository.get_all()

    assert result == [movement]

    statement = db.scalars.call_args.args[0]

    compiled = statement.compile()

    assert compiled.params["param_1"] == 50
    assert compiled.params["param_2"] == 0


@pytest.mark.parametrize(
    "offset,limit",
    [
        (-1, 50),
        (0, 0),
        (0, 101),
    ],
)
def test_get_all_invalid_pagination(repository, offset, limit):
    with pytest.raises(ValueError):
        repository.get_all(offset=offset, limit=limit)


def test_get_all_with_filters(repository, db):
    db.scalars.return_value.all.return_value = []

    repository.get_all(
        offset=10,
        limit=20,
        product_id=1,
        user_id=2,
        supplier_id=3,
        movement_type="receipt",
    )

    statement = db.scalars.call_args.args[0]
    compiled = statement.compile()

    params = compiled.params

    assert 1 in params.values()
    assert 2 in params.values()
    assert 3 in params.values()
    assert "receipt" in params.values()
    assert 10 in params.values()
    assert 20 in params.values()


def test_get_all_orders_newest_first(repository, db):
    db.scalars.return_value.all.return_value = []

    repository.get_all()

    statement = db.scalars.call_args.args[0]

    order_by = [
        str(item)
        for item in statement._order_by_clauses
    ]

    assert "stock_movements.created_at DESC" in order_by
    assert "stock_movements.id DESC" in order_by


def test_create_movement(repository, db):
    movement = repository.create(
        product_id=1,
        user_id=2,
        movement_type="receipt",
        quantity=Decimal("10.000"),
        supplier_id=3,
        note="Delivery",
    )

    assert isinstance(movement, StockMovement)
    assert movement.product_id == 1
    assert movement.user_id == 2
    assert movement.movement_type == "receipt"
    assert movement.quantity == Decimal("10.000")
    assert movement.supplier_id == 3
    assert movement.note == "Delivery"

    db.add.assert_called_once_with(movement)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_movement_optional_fields(repository, db):
    movement = repository.create(
        product_id=1,
        user_id=2,
        movement_type="issue",
        quantity=Decimal("2.500"),
    )

    assert movement.supplier_id is None
    assert movement.note is None


@pytest.mark.parametrize(
    "quantity",
    [
        Decimal("0"),
        Decimal("-1"),
    ],
)
def test_increase_stock_invalid_quantity(repository, db, quantity):
    with pytest.raises(ValueError):
        repository.increase_stock(1, quantity)

    db.execute.assert_not_called()


@pytest.mark.parametrize(
    "quantity",
    [
        Decimal("0"),
        Decimal("-1"),
    ],
)
def test_decrease_stock_invalid_quantity(repository, db, quantity):
    with pytest.raises(ValueError):
        repository.decrease_stock(1, quantity)

    db.execute.assert_not_called()


def test_increase_stock_success(repository, db):
    db.execute.return_value.rowcount = 1

    result = repository.increase_stock(
        1,
        Decimal("5.000"),
    )

    assert result is True

    statement = db.execute.call_args.args[0]

    assert isinstance(statement, Update)
    assert statement.table.name == "products"
    db.commit.assert_not_called()


def test_increase_stock_no_row_updated(repository, db):
    db.execute.return_value.rowcount = 0

    result = repository.increase_stock(
        1,
        Decimal("5.000"),
    )

    assert result is False


def test_decrease_stock_success(repository, db):
    db.execute.return_value.rowcount = 1

    result = repository.decrease_stock(
        1,
        Decimal("3.000"),
    )

    assert result is True

    statement = db.execute.call_args.args[0]

    assert isinstance(statement, Update)
    assert statement.table.name == "products"
    db.commit.assert_not_called()


def test_decrease_stock_insufficient_quantity(repository, db):
    db.execute.return_value.rowcount = 0

    result = repository.decrease_stock(
        1,
        Decimal("100.000"),
    )

    assert result is False


def test_increase_stock_has_upper_bound(repository, db):
    db.execute.return_value.rowcount = 1

    repository.increase_stock(
        1,
        Decimal("1.000"),
    )

    statement = db.execute.call_args.args[0]
    sql = str(statement.compile())

    assert "products.quantity <=" in sql


def test_decrease_stock_has_balance_condition(repository, db):
    db.execute.return_value.rowcount = 1

    repository.decrease_stock(
        1,
        Decimal("1.000"),
    )

    statement = db.execute.call_args.args[0]
    sql = str(statement.compile())

    assert "products.quantity >=" in sql
