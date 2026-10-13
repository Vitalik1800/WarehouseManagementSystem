from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.schemas.stock_movements import (
    StockBalanceResponse,
    StockMovementCreate,
    StockMovementResponse,
)


def valid_payload(**overrides):
    payload = {
        "product_id": 1,
        "movement_type": "receipt",
        "quantity": "10.000",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "movement_type,note",
    [
        ("receipt", None),
        ("issue", None),
        ("writeoff", "Damaged goods"),
    ],
)
def test_valid_movement_types(movement_type, note):
    data = StockMovementCreate.model_validate(
        valid_payload(
            movement_type=movement_type,
            note=note,
        )
    )

    assert data.movement_type == movement_type
    assert data.quantity == Decimal("10.000")


def test_receipt_with_supplier():
    data = StockMovementCreate.model_validate(
        valid_payload(supplier_id=5)
    )

    assert data.supplier_id == 5


@pytest.mark.parametrize(
    "quantity",
    [
        "0",
        "-1",
        "-0.001",
        "0.000",
    ],
)
def test_nonpositive_quantity_rejected(quantity):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(quantity=quantity)
        )


@pytest.mark.parametrize(
    "quantity",
    [
        "1.0001",
        "0.0001",
        "99999999999.9999",
    ],
)
def test_excess_decimal_places_rejected(quantity):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(quantity=quantity)
        )


def test_maximum_supported_quantity():
    data = StockMovementCreate.model_validate(
        valid_payload(quantity="99999999999.999")
    )

    assert data.quantity == Decimal("99999999999.999")


def test_quantity_exceeding_precision_rejected():
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(quantity="100000000000.000")
        )


@pytest.mark.parametrize(
    "quantity",
    [
        True,
        False,
        "NaN",
        "Infinity",
        "-Infinity",
        "not-a-number",
    ],
)
def test_invalid_quantity_rejected(quantity):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(quantity=quantity)
        )


@pytest.mark.parametrize(
    "product_id",
    [
        0,
        -1,
        True,
        False,
        None,
    ],
)
def test_invalid_product_id_rejected(product_id):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(product_id=product_id)
        )


@pytest.mark.parametrize(
    "supplier_id",
    [
        0,
        -1,
        True,
        False,
    ],
)
def test_invalid_supplier_id_rejected(supplier_id):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(supplier_id=supplier_id)
        )


@pytest.mark.parametrize(
    "movement_type",
    [
        "transfer",
        "return",
        "RECEIPT",
        "",
        None,
    ],
)
def test_invalid_movement_type_rejected(movement_type):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(movement_type=movement_type)
        )


@pytest.mark.parametrize(
    "note",
    [
        None,
        "",
        " ",
        "\t\n",
    ],
)
def test_writeoff_requires_reason(note):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(
                movement_type="writeoff",
                note=note,
            )
        )


@pytest.mark.parametrize(
    "movement_type",
    [
        "issue",
        "writeoff",
    ],
)
def test_supplier_for_nonreceipt_rejected(movement_type):
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(
                movement_type=movement_type,
                supplier_id=3,
                note="Damaged" if movement_type == "writeoff" else None,
            )
        )


def test_note_is_trimmed():
    data = StockMovementCreate.model_validate(
        valid_payload(note="  Delivery received  ")
    )

    assert data.note == "Delivery received"


def test_blank_note_normalized_to_none():
    data = StockMovementCreate.model_validate(
        valid_payload(note="   ")
    )

    assert data.note is None


def test_nonstring_note_rejected():
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(note=123)
        )


def test_extra_fields_rejected():
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate(
            valid_payload(user_id=7)
        )


def test_missing_required_fields_rejected():
    with pytest.raises(ValidationError):
        StockMovementCreate.model_validate({})


def test_movement_response_from_attributes():
    class Movement:
        id = 1
        product_id = 2
        user_id = 3
        supplier_id = None
        movement_type = "issue"
        quantity = Decimal("5.500")
        created_at = datetime(2026, 10, 12, 12, 0)
        note = "Customer order"

    result = StockMovementResponse.model_validate(Movement())

    assert result.id == 1
    assert result.product_id == 2
    assert result.quantity == Decimal("5.500")
    assert result.movement_type == "issue"


def test_balance_response_from_attributes():
    class Balance:
        product_id = 1
        sku = "SKU-001"
        name = "Test product"
        unit = "pcs"
        quantity = Decimal("125.000")

    result = StockBalanceResponse.model_validate(Balance())

    assert result.product_id == 1
    assert result.quantity == Decimal("125.000")
    assert result.sku == "SKU-001"
