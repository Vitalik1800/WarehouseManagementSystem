from unittest.mock import Mock

import pytest

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from backend.app.models.supplier import Supplier
from backend.app.repositories.supplier_repository import (
    SupplierRepository,
)


def make_repository():
    db = Mock(spec=Session)
    repository = SupplierRepository(db)
    return db, repository


def compile_sql(statement):
    return str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


# ============================================================
# GET BY ID
# ============================================================


def test_get_by_id_success():
    db, repository = make_repository()

    supplier = Mock(spec=Supplier)
    db.get.return_value = supplier

    result = repository.get_by_id(1)

    assert result is supplier
    db.get.assert_called_once_with(Supplier, 1)


def test_get_by_id_not_found():
    db, repository = make_repository()

    db.get.return_value = None

    result = repository.get_by_id(999)

    assert result is None
    db.get.assert_called_once_with(Supplier, 999)


# ============================================================
# GET ALL
# ============================================================


def test_get_all_default_pagination():
    db, repository = make_repository()

    suppliers = [
        Mock(spec=Supplier),
        Mock(spec=Supplier),
    ]

    db.scalars.return_value.all.return_value = suppliers

    result = repository.get_all()

    assert result == suppliers

    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]
    sql = compile_sql(statement)

    assert "FROM suppliers" in sql
    assert "ORDER BY suppliers.id" in sql
    assert "LIMIT 0, 50" in sql


def test_get_all_custom_pagination():
    db, repository = make_repository()

    suppliers = [Mock(spec=Supplier)]

    db.scalars.return_value.all.return_value = suppliers

    result = repository.get_all(
        offset=10,
        limit=5,
    )

    assert result == suppliers

    statement = db.scalars.call_args.args[0]
    sql = compile_sql(statement)

    assert "ORDER BY suppliers.id" in sql
    assert "LIMIT 10, 5" in sql


def test_get_all_empty_result():
    db, repository = make_repository()

    db.scalars.return_value.all.return_value = []

    result = repository.get_all()

    assert result == []
    db.scalars.assert_called_once()


@pytest.mark.parametrize(
    "offset",
    [-1, -10, -100],
)
def test_get_all_negative_offset(offset):
    db, repository = make_repository()

    with pytest.raises(
        ValueError,
        match="Offset must not be negative",
    ):
        repository.get_all(offset=offset)

    db.scalars.assert_not_called()


@pytest.mark.parametrize(
    "limit",
    [0, -1, 101],
)
def test_get_all_invalid_limit(limit):
    db, repository = make_repository()

    with pytest.raises(
        ValueError,
        match="Limit must be between 1 and 100",
    ):
        repository.get_all(limit=limit)

    db.scalars.assert_not_called()


# ============================================================
# CREATE
# ============================================================


def test_create_supplier_all_fields():
    db, repository = make_repository()

    supplier = repository.create(
        name="Test Supplier",
        contact_person="John Smith",
        phone="+380501234567",
        email="supplier@example.com",
        address="Kyiv, Ukraine",
    )

    assert isinstance(supplier, Supplier)
    assert supplier.name == "Test Supplier"
    assert supplier.contact_person == "John Smith"
    assert supplier.phone == "+380501234567"
    assert supplier.email == "supplier@example.com"
    assert supplier.address == "Kyiv, Ukraine"

    db.add.assert_called_once_with(supplier)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_supplier_only_required_fields():
    db, repository = make_repository()

    supplier = repository.create(
        name="Test Supplier"
    )

    assert isinstance(supplier, Supplier)
    assert supplier.name == "Test Supplier"
    assert supplier.contact_person is None
    assert supplier.phone is None
    assert supplier.email is None
    assert supplier.address is None

    db.add.assert_called_once_with(supplier)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_supplier_flush_error():
    db, repository = make_repository()

    db.flush.side_effect = RuntimeError(
        "Flush failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Flush failure",
    ):
        repository.create(
            name="Test Supplier"
        )

    db.add.assert_called_once()
    db.flush.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# HAS STOCK MOVEMENTS
# ============================================================


def test_has_stock_movements_true():
    db, repository = make_repository()

    db.scalar.return_value = True

    result = repository.has_stock_movements(1)

    assert result is True
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    sql = compile_sql(statement)

    assert "EXISTS" in sql.upper()
    assert "stock_movements.supplier_id = 1" in sql


def test_has_stock_movements_false():
    db, repository = make_repository()

    db.scalar.return_value = False

    result = repository.has_stock_movements(1)

    assert result is False
    db.scalar.assert_called_once()


def test_has_stock_movements_none():
    db, repository = make_repository()

    db.scalar.return_value = None

    result = repository.has_stock_movements(1)

    assert result is False
    db.scalar.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_supplier():
    db, repository = make_repository()

    supplier = Mock(spec=Supplier)

    repository.delete(supplier)

    db.delete.assert_called_once_with(supplier)
    db.commit.assert_not_called()
