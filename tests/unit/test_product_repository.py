from unittest.mock import Mock

import pytest

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from backend.app.models.product import Product
from backend.app.repositories.product_repository import (
    ProductRepository,
)


def make_repository():
    db = Mock(spec=Session)
    repository = ProductRepository(db)
    db.scalars.return_value.all.return_value = []
    return db, repository


def compile_sql(statement):
    return str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def get_sql(db):
    db.scalars.assert_called_once()
    statement = db.scalars.call_args.args[0]
    return compile_sql(statement)


# ============================================================
# DEFAULT RESULTS AND PAGINATION
# ============================================================


def test_get_all_default_pagination():
    db, repository = make_repository()

    products = [
        Mock(spec=Product),
        Mock(spec=Product),
    ]
    db.scalars.return_value.all.return_value = products

    assert repository.get_all() == products

    sql = get_sql(db)

    assert "FROM products" in sql
    assert "ORDER BY products.id" in sql
    assert "LIMIT 0, 50" in sql


def test_get_all_custom_pagination():
    db, repository = make_repository()

    assert repository.get_all(offset=10, limit=25) == []

    sql = get_sql(db)

    assert "LIMIT 10, 25" in sql
    assert "ORDER BY products.id" in sql


def test_get_all_empty_result():
    db, repository = make_repository()

    assert repository.get_all() == []
    db.scalars.assert_called_once()


@pytest.mark.parametrize("limit", [1, 50, 100])
def test_get_all_valid_limits(limit):
    db, repository = make_repository()

    repository.get_all(limit=limit)

    assert f"LIMIT 0, {limit}" in get_sql(db)


@pytest.mark.parametrize("offset", [-1, -10, -100])
def test_get_all_negative_offset(offset):
    db, repository = make_repository()

    with pytest.raises(
            ValueError,
            match="Offset must not be negative",
    ):
        repository.get_all(offset=offset)

    db.scalars.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_get_all_invalid_limit(limit):
    db, repository = make_repository()

    with pytest.raises(
            ValueError,
            match="Limit must be between 1 and 100",
    ):
        repository.get_all(limit=limit)

    db.scalars.assert_not_called()


# ============================================================
# SEARCH BY NAME AND SKU
# ============================================================


def test_get_all_search_by_name_and_sku():
    db, repository = make_repository()

    repository.get_all(search="Samsung")

    sql = get_sql(db)

    assert "products.name" in sql
    assert "products.sku" in sql
    assert "LIKE" in sql.upper()
    assert "OR" in sql.upper()
    assert "%Samsung%" in sql


def test_get_all_search_is_case_insensitive():
    db, repository = make_repository()

    repository.get_all(search="sAmSuNg")

    sql = get_sql(db)

    assert "lower(products.name)" in sql.lower()
    assert "lower(products.sku)" in sql.lower()
    assert "%sAmSuNg%" in sql


def test_get_all_search_trims_whitespace():
    db, repository = make_repository()

    repository.get_all(search="  Samsung  ")

    sql = get_sql(db)

    assert "%Samsung%" in sql
    assert "%  Samsung  %" not in sql


@pytest.mark.parametrize("search", ["", " ", "   "])
def test_get_all_blank_search_ignored(search):
    db, repository = make_repository()

    repository.get_all(search=search)

    sql = get_sql(db)

    assert " LIKE " not in sql.upper()
    assert "ORDER BY products.id" in sql


@pytest.mark.parametrize(
    ("search", "escaped"),
    [
        ("50%", r"50\%"),
        ("item_name", r"item\_name"),
        (r"folder\item", r"folder\\item"),
    ],
)
def test_get_all_search_escapes_special_characters(
        search,
        escaped,
):
    db, repository = make_repository()

    repository.get_all(search=search)

    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]
    compiled = statement.compile(
        dialect=mysql.dialect()
    )

    parameter_values = list(compiled.params.values())

    expected_pattern = f"%{escaped}%"

    assert parameter_values.count(expected_pattern) == 2

    sql = str(compiled)

    assert "ESCAPE" in sql.upper()


# ============================================================
# EXACT SKU FILTER
# ============================================================


def test_get_all_filter_by_sku():
    db, repository = make_repository()

    repository.get_all(sku="SKU-001")

    sql = get_sql(db)

    assert "products.sku = 'SKU-001'" in sql


def test_get_all_sku_filter_is_exact():
    db, repository = make_repository()

    repository.get_all(sku="SKU-001")

    sql = get_sql(db)

    assert "products.sku = 'SKU-001'" in sql
    assert " LIKE " not in sql.upper()


# ============================================================
# CATEGORY AND LOCATION FILTERS
# ============================================================


def test_get_all_filter_by_category():
    db, repository = make_repository()

    repository.get_all(category_id=3)

    sql = get_sql(db)

    assert "products.category_id = 3" in sql


def test_get_all_filter_by_location():
    db, repository = make_repository()

    repository.get_all(location_id=5)

    sql = get_sql(db)

    assert "products.location_id = 5" in sql


def test_get_all_combined_filters():
    db, repository = make_repository()

    repository.get_all(
        search="Samsung",
        sku="SKU-001",
        category_id=3,
        location_id=5,
        offset=10,
        limit=25,
    )

    sql = get_sql(db)

    assert "%Samsung%" in sql
    assert "products.sku = 'SKU-001'" in sql
    assert "products.category_id = 3" in sql
    assert "products.location_id = 5" in sql
    assert "ORDER BY products.id" in sql
    assert "LIMIT 10, 25" in sql


def test_get_all_large_offset():
    db, repository = make_repository()

    repository.get_all(offset=100000, limit=10)

    sql = get_sql(db)

    assert "LIMIT 100000, 10" in sql


# ============================================================
# GET BY ID
# ============================================================


def test_get_by_id_existing_product():
    db, repository = make_repository()
    product = Mock(spec=Product)
    db.get.return_value = product

    result = repository.get_by_id(15)

    assert result is product
    db.get.assert_called_once_with(Product, 15)


def test_get_by_id_missing_product():
    db, repository = make_repository()
    db.get.return_value = None

    assert repository.get_by_id(999) is None
    db.get.assert_called_once_with(Product, 999)


# ============================================================
# GET BY SKU
# ============================================================


def test_get_by_sku_existing_product():
    db, repository = make_repository()
    product = Mock(spec=Product)
    db.scalar.return_value = product

    result = repository.get_by_sku("SKU-001")

    assert result is product
    db.scalar.assert_called_once()

    sql = compile_sql(db.scalar.call_args.args[0])

    assert "FROM products" in sql
    assert "products.sku = 'SKU-001'" in sql


def test_get_by_sku_missing_product():
    db, repository = make_repository()
    db.scalar.return_value = None

    assert repository.get_by_sku("UNKNOWN") is None
    db.scalar.assert_called_once()


# ============================================================
# CREATE
# ============================================================


def test_create_product_success():
    from decimal import Decimal

    db, repository = make_repository()

    product = repository.create(
        sku="SKU-001",
        name="Test Product",
        category_id=2,
        location_id=3,
        unit="kg",
        description="Test description",
    )

    assert isinstance(product, Product)
    assert product.sku == "SKU-001"
    assert product.name == "Test Product"
    assert product.category_id == 2
    assert product.location_id == 3
    assert product.unit == "kg"
    assert product.description == "Test description"
    assert product.quantity == Decimal("0.000")

    db.add.assert_called_once_with(product)
    db.flush.assert_called_once()
    db.commit.assert_not_called()


def test_create_product_default_values():
    from decimal import Decimal

    db, repository = make_repository()

    product = repository.create(
        sku="SKU-002",
        name="Default Product",
        category_id=1,
        location_id=1,
    )

    assert product.unit == "pcs"
    assert product.description is None
    assert product.quantity == Decimal("0.000")

    db.add.assert_called_once_with(product)
    db.flush.assert_called_once()


def test_create_product_flush_error():
    db, repository = make_repository()
    db.flush.side_effect = RuntimeError("Flush failed")

    with pytest.raises(RuntimeError, match="Flush failed"):
        repository.create(
            sku="SKU-003",
            name="Failed Product",
            category_id=1,
            location_id=1,
        )

    db.add.assert_called_once()
    db.flush.assert_called_once()
    db.commit.assert_not_called()


# ============================================================
# STOCK MOVEMENTS
# ============================================================


def test_has_stock_movements_true():
    db, repository = make_repository()
    db.scalar.return_value = True

    assert repository.has_stock_movements(10) is True

    sql = compile_sql(db.scalar.call_args.args[0])

    assert "EXISTS" in sql.upper()
    assert "stock_movements.product_id = 10" in sql


def test_has_stock_movements_false():
    db, repository = make_repository()
    db.scalar.return_value = False

    assert repository.has_stock_movements(10) is False
    db.scalar.assert_called_once()


# ============================================================
# DELETE
# ============================================================


def test_delete_product_success():
    db, repository = make_repository()
    product = Mock(spec=Product)

    result = repository.delete(product)

    assert result is None
    db.delete.assert_called_once_with(product)
    db.commit.assert_not_called()


def test_delete_product_database_error():
    db, repository = make_repository()
    product = Mock(spec=Product)

    db.delete.side_effect = RuntimeError("Delete failed")

    with pytest.raises(RuntimeError, match="Delete failed"):
        repository.delete(product)

    db.delete.assert_called_once_with(product)
    db.commit.assert_not_called()
