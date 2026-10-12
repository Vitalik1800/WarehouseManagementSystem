from unittest.mock import Mock

import pytest

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from backend.app.models.storage_location import StorageLocation
from backend.app.repositories.storage_location_repository import (
    StorageLocationRepository,
)


def make_repository():
    db = Mock(spec=Session)
    repository = StorageLocationRepository(db)
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

    location = Mock(spec=StorageLocation)
    db.get.return_value = location

    result = repository.get_by_id(1)

    assert result is location
    db.get.assert_called_once_with(StorageLocation, 1)


def test_get_by_id_not_found():
    db, repository = make_repository()

    db.get.return_value = None

    result = repository.get_by_id(999)

    assert result is None
    db.get.assert_called_once_with(StorageLocation, 999)


# ============================================================
# GET BY NAME
# ============================================================


def test_get_by_name_success():
    db, repository = make_repository()

    location = Mock(spec=StorageLocation)
    db.scalar.return_value = location

    result = repository.get_by_name("Warehouse A")

    assert result is location
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    sql = compile_sql(statement)

    assert "FROM storage_locations" in sql
    assert "storage_locations.name = 'Warehouse A'" in sql


def test_get_by_name_not_found():
    db, repository = make_repository()

    db.scalar.return_value = None

    result = repository.get_by_name("Unknown")

    assert result is None
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    sql = compile_sql(statement)

    assert "storage_locations.name = 'Unknown'" in sql


# ============================================================
# GET ALL
# ============================================================


def test_get_all_default_pagination():
    db, repository = make_repository()

    locations = [
        Mock(spec=StorageLocation),
        Mock(spec=StorageLocation),
    ]

    db.scalars.return_value.all.return_value = locations

    result = repository.get_all()

    assert result == locations
    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]
    sql = compile_sql(statement)

    assert "FROM storage_locations" in sql
    assert "ORDER BY storage_locations.id" in sql
    assert "LIMIT 0, 50" in sql


def test_get_all_custom_pagination():
    db, repository = make_repository()

    locations = [Mock(spec=StorageLocation)]

    db.scalars.return_value.all.return_value = locations

    result = repository.get_all(
        offset=10,
        limit=5,
    )

    assert result == locations

    statement = db.scalars.call_args.args[0]
    sql = compile_sql(statement)

    assert "ORDER BY storage_locations.id" in sql
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


def test_create_location_success():
    db, repository = make_repository()

    location = repository.create(
        name="Warehouse A",
        description="Main warehouse",
    )

    assert isinstance(location, StorageLocation)
    assert location.name == "Warehouse A"
    assert location.description == "Main warehouse"

    db.add.assert_called_once_with(location)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_location_without_description():
    db, repository = make_repository()

    location = repository.create(
        name="Warehouse A"
    )

    assert isinstance(location, StorageLocation)
    assert location.name == "Warehouse A"
    assert location.description is None

    db.add.assert_called_once_with(location)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_location_flush_error():
    db, repository = make_repository()

    db.flush.side_effect = RuntimeError(
        "Flush failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Flush failure",
    ):
        repository.create(
            name="Warehouse A"
        )

    db.add.assert_called_once()
    db.flush.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# HAS PRODUCTS
# ============================================================


def test_has_products_true():
    db, repository = make_repository()

    db.scalar.return_value = True

    result = repository.has_products(1)

    assert result is True
    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    sql = compile_sql(statement)

    assert "EXISTS" in sql.upper()
    assert "products.location_id = 1" in sql


def test_has_products_false():
    db, repository = make_repository()

    db.scalar.return_value = False

    result = repository.has_products(1)

    assert result is False
    db.scalar.assert_called_once()


def test_has_products_none():
    db, repository = make_repository()

    db.scalar.return_value = None

    result = repository.has_products(1)

    assert result is False
    db.scalar.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_location():
    db, repository = make_repository()

    location = Mock(spec=StorageLocation)

    repository.delete(location)

    db.delete.assert_called_once_with(location)
    db.commit.assert_not_called()
