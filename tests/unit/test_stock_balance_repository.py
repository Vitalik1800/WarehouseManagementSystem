from unittest.mock import Mock

import pytest

from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from backend.app.models.product import Product
from backend.app.repositories.product_repository import (
    ProductRepository
)

from decimal import Decimal


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


def test_get_stock_balances_default_pagination():
    db = Mock(spec=Session)
    repository = ProductRepository(db)

    products = [
        Mock(spec=Product),
        Mock(spec=Product),
    ]

    db.scalars.return_value.all.return_value = products

    result = repository.get_stock_balances()

    assert result == products

    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]

    sql = str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "FROM products" in sql
    assert "ORDER BY products.id" in sql
    assert "LIMIT 0, 50" in sql

    db.commit.assert_not_called()
    db.flush.assert_not_called()


@pytest.mark.parametrize(
    ("stock_status", "expected_condition"),
    [
        ("in_stock", "products.quantity > 0"),
        ("out_of_stock", "products.quantity = 0"),
    ],
)
def test_get_stock_balances_filters_by_stock_status(
        stock_status,
        expected_condition,
):
    db = Mock(spec=Session)
    repository = ProductRepository(db)
    db.scalars.return_value.all.return_value = []

    repository.get_stock_balances(
        stock_status=stock_status,
    )

    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]

    sql = str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert expected_condition in sql
    assert "ORDER BY products.id" in sql


def test_get_stock_balances_rejects_invalid_stock_status():
    db = Mock(spec=Session)
    repository = ProductRepository(db)

    with pytest.raises(
            ValueError,
            match="Invalid stock status",
    ):
        repository.get_stock_balances(
            stock_status="unknown",
        )

    db.scalars.assert_not_called()


@pytest.mark.parametrize("limit", [1, 50, 100])
def test_get_stock_balances_valid_limits(limit):
    db = Mock(spec=Session)
    repository = ProductRepository(db)
    db.scalars.return_value.all.return_value = []

    repository.get_stock_balances(limit=limit)

    statement = db.scalars.call_args.args[0]
    sql = str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert f"LIMIT 0, {limit}" in sql


@pytest.mark.parametrize("offset", [-1, -10, -100])
def test_get_stock_balances_rejects_negative_offset(offset):
    db = Mock(spec=Session)
    repository = ProductRepository(db)

    with pytest.raises(
            ValueError,
            match="Offset must not be negative",
    ):
        repository.get_stock_balances(offset=offset)

    db.scalars.assert_not_called()


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_get_stock_balances_rejects_invalid_limit(limit):
    db = Mock(spec=Session)
    repository = ProductRepository(db)

    with pytest.raises(
            ValueError,
            match="Limit must be between 1 and 100",
    ):
        repository.get_stock_balances(limit=limit)

    db.scalars.assert_not_called()


def test_get_stock_balances_custom_pagination():
    db = Mock(spec=Session)
    repository = ProductRepository(db)
    db.scalars.return_value.all.return_value = []

    repository.get_stock_balances(offset=20, limit=25)

    statement = db.scalars.call_args.args[0]
    sql = str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "LIMIT 20, 25" in sql
    assert "ORDER BY products.id" in sql


def test_get_stock_balances_filter_by_category():
    db = Mock(spec=Session)
    repository = ProductRepository(db)
    db.scalars.return_value.all.return_value = []

    repository.get_stock_balances(category_id=3)

    sql = str(
        db.scalars.call_args.args[0].compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "products.category_id = 3" in sql


def test_get_stock_balances_filter_by_location():
    db = Mock(spec=Session)
    repository = ProductRepository(db)
    db.scalars.return_value.all.return_value = []

    repository.get_stock_balances(location_id=5)

    sql = str(
        db.scalars.call_args.args[0].compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "products.location_id = 5" in sql


def test_get_stock_balances_combined_filters():
    db = Mock(spec=Session)
    repository = ProductRepository(db)
    db.scalars.return_value.all.return_value = []

    repository.get_stock_balances(
        category_id=3,
        location_id=5,
        stock_status="in_stock",
        offset=10,
        limit=25,
    )

    sql = str(
        db.scalars.call_args.args[0].compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "products.category_id = 3" in sql
    assert "products.location_id = 5" in sql
    assert "products.quantity > 0" in sql
    assert "ORDER BY products.id" in sql
    assert "LIMIT 10, 25" in sql


@pytest.mark.parametrize(
    ("search", "expected_pattern"),
    [
        ("Laptop", "%Laptop%"),
        ("  Monitor  ", "%Monitor%"),
        ("SKU-123", "%SKU-123%"),
    ],
)
def test_get_stock_balances_search_by_name_or_sku(
        search,
        expected_pattern,
):
    db, repository = make_repository()

    repository.get_stock_balances(search=search)

    sql = get_sql(db)

    assert "products.name" in sql
    assert "products.sku" in sql
    assert "LIKE" in sql
    assert expected_pattern in sql


@pytest.mark.parametrize(
    ("search", "expected_pattern"),
    [
        ("50%", r"%50\%%"),
        ("A_B", r"%A\_B%"),
        (r"A\B", r"%A\\B%"),
    ],
)
def test_get_stock_balances_escapes_search_wildcards(
        search,
        expected_pattern,
):
    db, repository = make_repository()

    repository.get_stock_balances(search=search)

    db.scalars.assert_called_once()

    statement = db.scalars.call_args.args[0]

    compiled = statement.compile(
        dialect=mysql.dialect(),
    )

    parameter_values = list(compiled.params.values())

    assert expected_pattern in parameter_values

    sql = str(compiled)

    assert "ESCAPE" in sql
    assert "products.name" in sql
    assert "products.sku" in sql


def test_get_stock_balances_combines_search_with_filters():
    db, repository = make_repository()

    repository.get_stock_balances(
        search="Laptop",
        category_id=3,
        location_id=5,
        stock_status="in_stock",
        offset=10,
        limit=25,
    )

    sql = get_sql(db)

    assert "products.name" in sql
    assert "products.sku" in sql
    assert "products.category_id = 3" in sql
    assert "products.location_id = 5" in sql
    assert "products.quantity > 0" in sql
    assert "LIMIT 10, 25" in sql


@pytest.mark.parametrize("search", ["", "   "])
def test_get_stock_balances_ignores_empty_search(search):
    db, repository = make_repository()

    repository.get_stock_balances(search=search)

    sql = get_sql(db)

    assert " LIKE " not in sql
    assert "ORDER BY products.id" in sql


@pytest.mark.parametrize(
    ("min_quantity", "expected_condition"),
    [
        (Decimal("10"), "products.quantity >= 10"),
        (Decimal("0.125"), "products.quantity >= 0.125"),
    ],
)
def test_get_stock_balances_min_quantity(
    min_quantity,
    expected_condition,
):
    db, repository = make_repository()

    repository.get_stock_balances(
        min_quantity=min_quantity,
    )

    assert expected_condition in get_sql(db)


@pytest.mark.parametrize(
    ("max_quantity", "expected_condition"),
    [
        (Decimal("50"), "products.quantity <= 50"),
        (Decimal("10.500"), "products.quantity <= 10.500"),
    ],
)
def test_get_stock_balances_max_quantity(
    max_quantity,
    expected_condition,
):
    db, repository = make_repository()

    repository.get_stock_balances(
        max_quantity=max_quantity,
    )

    assert expected_condition in get_sql(db)


def test_get_stock_balances_quantity_range():
    db, repository = make_repository()

    repository.get_stock_balances(
        min_quantity=Decimal("10"),
        max_quantity=Decimal("50"),
    )

    sql = get_sql(db)

    assert "products.quantity >= 10" in sql
    assert "products.quantity <= 50" in sql


@pytest.mark.parametrize(
    ("min_quantity", "max_quantity"),
    [
        (Decimal("-1"), None),
        (None, Decimal("-0.001")),
    ],
)
def test_get_stock_balances_rejects_negative_quantity(
    min_quantity,
    max_quantity,
):
    db, repository = make_repository()

    with pytest.raises(
        ValueError,
        match="Quantity must not be negative",
    ):
        repository.get_stock_balances(
            min_quantity=min_quantity,
            max_quantity=max_quantity,
        )

    db.scalars.assert_not_called()


def test_get_stock_balances_rejects_invalid_quantity_range():
    db, repository = make_repository()

    with pytest.raises(
        ValueError,
        match="Minimum quantity must not exceed maximum quantity",
    ):
        repository.get_stock_balances(
            min_quantity=Decimal("100"),
            max_quantity=Decimal("10"),
        )

    db.scalars.assert_not_called()


@pytest.mark.parametrize(
    "invalid_quantity",
    [
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
@pytest.mark.parametrize(
    "parameter_name",
    ["min_quantity", "max_quantity"],
)
def test_get_stock_balances_rejects_non_finite_quantity(
    invalid_quantity,
    parameter_name,
):
    db, repository = make_repository()

    with pytest.raises(
        ValueError,
        match="Quantity must be finite",
    ):
        repository.get_stock_balances(
            **{parameter_name: invalid_quantity}
        )

    db.scalars.assert_not_called()


@pytest.mark.parametrize(
    ("sort_by", "expected_order"),
    [
        ("id", "ORDER BY products.id"),
        (
            "quantity_asc",
            "ORDER BY products.quantity ASC, products.id",
        ),
        (
            "quantity_desc",
            "ORDER BY products.quantity DESC, products.id",
        ),
    ],
)
def test_get_stock_balances_sorting(
    sort_by,
    expected_order,
):
    db, repository = make_repository()

    repository.get_stock_balances(sort_by=sort_by)

    sql = get_sql(db)

    assert expected_order in sql


def test_get_stock_balances_sorting_with_filters():
    db, repository = make_repository()

    repository.get_stock_balances(
        stock_status="in_stock",
        min_quantity=Decimal("10"),
        sort_by="quantity_desc",
        offset=20,
        limit=25,
    )

    sql = get_sql(db)

    assert "products.quantity > 0" in sql
    assert "products.quantity >= 10" in sql
    assert "ORDER BY products.quantity DESC, products.id" in sql
    assert "LIMIT 20, 25" in sql


@pytest.mark.parametrize(
    "sort_by",
    ["unknown", "name", "", "quantity"],
)
def test_get_stock_balances_rejects_invalid_sorting(sort_by):
    db, repository = make_repository()

    with pytest.raises(
        ValueError,
        match="Invalid sort field",
    ):
        repository.get_stock_balances(sort_by=sort_by)

    db.scalars.assert_not_called()
