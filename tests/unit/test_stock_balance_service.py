
from decimal import Decimal
from unittest.mock import Mock

import pytest

from backend.app.services.stock_balance_service import (
    StockBalanceService
)


def make_service():
    db = Mock()
    service = StockBalanceService(db)

    service.products.get_stock_balances = Mock(return_value=[])

    return db, service


def make_product(
    product_id=1,
    sku="SKU-001",
    quantity="10.000",
):
    product = Mock()
    product.id = product_id
    product.sku = sku
    product.quantity = Decimal(quantity)
    return product


def test_list_stock_balances_default():
    db, service = make_service()

    products = [
        make_product(1, "SKU-001", "10.000"),
        make_product(2, "SKU-002", "0.000"),
    ]

    service.products.get_stock_balances.return_value = products

    result = service.list_stock_balances()

    assert result is products

    service.products.get_stock_balances.assert_called_once_with(
        offset=0,
        limit=50,
        stock_status=None,
        category_id=None,
        location_id=None,
        search=None,
        min_quantity=None,
        max_quantity=None,
        sort_by="id",
    )

    db.commit.assert_not_called()
    db.flush.assert_not_called()
    db.rollback.assert_not_called()


def test_list_stock_balances_with_filters():
    db, service = make_service()

    products = [make_product(quantity="25.000")]
    service.products.get_stock_balances.return_value = products

    result = service.list_stock_balances(
        offset=10,
        limit=20,
        stock_status="in_stock",
        category_id=2,
        location_id=3,
        search="phone",
        min_quantity=Decimal("10"),
        max_quantity=Decimal("100"),
        sort_by="quantity_desc",
    )

    assert result is products

    service.products.get_stock_balances.assert_called_once_with(
        offset=10,
        limit=20,
        stock_status="in_stock",
        category_id=2,
        location_id=3,
        search="phone",
        min_quantity=Decimal("10"),
        max_quantity=Decimal("100"),
        sort_by="quantity_desc",
    )

    db.commit.assert_not_called()
    db.flush.assert_not_called()


def test_list_stock_balances_empty_result():
    db, service = make_service()

    assert service.list_stock_balances() == []

    service.products.get_stock_balances.assert_called_once()
    db.commit.assert_not_called()


@pytest.mark.parametrize(
    "sort_by",
    [
        "id",
        "quantity_asc",
        "quantity_desc",
    ],
)
def test_list_stock_balances_sorting(sort_by):
    db, service = make_service()

    service.list_stock_balances(sort_by=sort_by)

    assert (
        service.products.get_stock_balances.call_args.kwargs["sort_by"]
        == sort_by
    )


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("offset", -1),
        ("limit", 0),
        ("limit", 101),
        ("stock_status", "unknown"),
        ("sort_by", "unknown"),
        ("min_quantity", Decimal("-1")),
        ("max_quantity", Decimal("-1")),
        ("min_quantity", Decimal("NaN")),
        ("max_quantity", Decimal("Infinity")),
    ],
)
def test_list_stock_balances_propagates_validation_errors(
    parameter,
    value,
):
    db, service = make_service()

    service.products.get_stock_balances.side_effect = ValueError(
        "Invalid stock balance filter"
    )

    with pytest.raises(
        ValueError,
        match="Invalid stock balance filter",
    ):
        service.list_stock_balances(**{parameter: value})

    service.products.get_stock_balances.assert_called_once()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()


def test_list_stock_balances_repository_error():
    db, service = make_service()

    service.products.get_stock_balances.side_effect = RuntimeError(
        "Database read failed"
    )

    with pytest.raises(
        RuntimeError,
        match="Database read failed",
    ):
        service.list_stock_balances()

    db.commit.assert_not_called()
    db.rollback.assert_not_called()
