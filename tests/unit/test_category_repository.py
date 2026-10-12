from unittest.mock import Mock

import pytest

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from backend.app.models.category import Category
from backend.app.repositories.category_repository import (
    CategoryRepository,
)


def make_repository():
    db = Mock(spec=Session)
    repository = CategoryRepository(db)
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

    category = Mock(spec=Category)
    db.get.return_value = category

    result = repository.get_by_id(1)

    assert result is category
    db.get.assert_called_once_with(Category, 1)


def test_get_by_id_not_found():
    db, repository = make_repository()

    db.get.return_value = None

    result = repository.get_by_id(999)

    assert result is None
    db.get.assert_called_once_with(Category, 999)


# ============================================================
# GET BY NAME
# ============================================================


def test_get_by_name_success():
    db, repository = make_repository()

    category = Mock(spec=Category)
    db.scalar.return_value = category

    result = repository.get_by_name("Electronics")

    assert result is category

    db.scalar.assert_called_once()

    statement = db.scalar.call_args.args[0]
    sql = compile_sql(statement)

    assert "FROM categories" in sql
    assert "categories.name = 'Electronics'" in sql


def test_get_by_name_not_found():
    db, repository = make_repository()

    db.scalar.return_value = None

    result = repository.get_by_name("Unknown")

    assert result is None
    db.scalar.assert_called_once()


# ============================================================
# GET ALL
# ============================================================


def test_get_all_default_pagination():
    db, repository = make_repository()

    categories = [
        Mock(spec=Category),
        Mock(spec=Category),
    ]

    db.scalars.return_value.all.return_value = categories

    result = repository.get_all()

    assert result == categories

    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]
    sql = compile_sql(statement)

    assert "ORDER BY categories.id" in sql
    assert "LIMIT 0, 50" in sql


def test_get_all_custom_pagination():
    db, repository = make_repository()

    categories = [Mock(spec=Category)]

    db.scalars.return_value.all.return_value = categories

    result = repository.get_all(
        offset=10,
        limit=5,
    )

    assert result == categories

    statement = db.scalars.call_args.args[0]
    sql = compile_sql(statement)

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


def test_create_category_success():
    db, repository = make_repository()

    category = repository.create(
        name="Electronics",
        description="Electronic products",
    )

    assert isinstance(category, Category)
    assert category.name == "Electronics"
    assert category.description == "Electronic products"

    db.add.assert_called_once_with(category)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_category_without_description():
    db, repository = make_repository()

    category = repository.create(
        name="Electronics"
    )

    assert isinstance(category, Category)
    assert category.name == "Electronics"
    assert category.description is None

    db.add.assert_called_once_with(category)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_category_flush_error():
    db, repository = make_repository()

    db.flush.side_effect = RuntimeError(
        "Flush failure"
    )

    with pytest.raises(
        RuntimeError,
        match="Flush failure",
    ):
        repository.create(
            name="Electronics"
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
    assert "products.category_id = 1" in sql


def test_has_products_false():
    db, repository = make_repository()

    db.scalar.return_value = False

    result = repository.has_products(1)

    assert result is False
    db.scalar.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_category():
    db, repository = make_repository()

    category = Mock(spec=Category)

    repository.delete(category)

    db.delete.assert_called_once_with(category)
    db.commit.assert_not_called()
