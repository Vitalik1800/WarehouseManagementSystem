
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.app.schemas.stock_balances import (
    StockBalanceResponse
)


def make_product(
    *,
    product_id=1,
    sku="SKU-001",
    name="Test Product",
    unit="pcs",
    quantity="12.500",
    category_id=2,
    location_id=3,
):
    return SimpleNamespace(
        id=product_id,
        sku=sku,
        name=name,
        unit=unit,
        quantity=Decimal(quantity),
        category_id=category_id,
        location_id=location_id,
    )


def test_stock_balance_from_attributes():
    product = make_product()

    result = StockBalanceResponse.model_validate(product)

    assert result.id == 1
    assert result.sku == "SKU-001"
    assert result.name == "Test Product"
    assert result.unit == "pcs"
    assert result.quantity == Decimal("12.500")
    assert result.category_id == 2
    assert result.location_id == 3


@pytest.mark.parametrize(
    "quantity",
    ["0.000", "0.001", "12.500", "999999.999"],
)
def test_stock_balance_decimal_precision(quantity):
    product = make_product(quantity=quantity)

    result = StockBalanceResponse.model_validate(product)

    assert result.quantity == Decimal(quantity)
    assert result.model_dump(mode="json")["quantity"] == quantity


def test_stock_balance_json_fields():
    product = make_product()

    result = StockBalanceResponse.model_validate(product)

    assert set(result.model_dump()) == {
        "id",
        "sku",
        "name",
        "unit",
        "quantity",
        "category_id",
        "location_id",
    }


def test_stock_balance_missing_required_field():
    product = make_product()
    del product.quantity

    with pytest.raises(ValidationError):
        StockBalanceResponse.model_validate(product)


def test_stock_balance_invalid_quantity():
    product = make_product()
    product.quantity = "not-a-number"

    with pytest.raises(ValidationError):
        StockBalanceResponse.model_validate(product)
