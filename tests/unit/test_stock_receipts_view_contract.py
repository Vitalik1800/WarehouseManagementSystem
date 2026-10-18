"""Headless contract checks for the receipts GUI."""
import pytest
from frontend.app.views.stock_receipts_view import StockReceiptsView


def test_payload_normalization():
    assert StockReceiptsView._build_payload(2, " 12.500 ", None, " note ") == {
        "product_id": 2, "quantity": "12.500", "supplier_id": None, "note": "note"
    }


@pytest.mark.parametrize("product,quantity,supplier,note", [
    (0, "1", None, ""), (True, "1", None, ""),
    (1, "", None, ""), (1, "1", 0, ""), (1, "1", True, ""),
])
def test_invalid_payload(product, quantity, supplier, note):
    with pytest.raises(ValueError):
        StockReceiptsView._build_payload(product, quantity, supplier, note)


def test_optional_fields():
    result = StockReceiptsView._build_payload(1, "1", 3, "  ")
    assert result["supplier_id"] == 3
    assert result["note"] is None
