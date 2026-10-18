"""Contract tests: no GUI window or database required."""
import pytest

from frontend.app.views._stock_outflow_view import StockOutflowView
from frontend.app.views.stock_issues_view import StockIssuesView
from frontend.app.views.stock_writeoffs_view import StockWriteoffsView


def test_types_and_actions():
    assert StockIssuesView.KIND == "issue"
    assert StockWriteoffsView.KIND == "writeoff"
    assert StockIssuesView.ACTION != StockWriteoffsView.ACTION


@pytest.mark.parametrize("kind", ["issue", "writeoff"])
def test_valid_payload(kind):
    result = StockOutflowView._build_payload(177, " 1.250 ", " test ", kind=kind)
    assert result == {"product_id": 177, "quantity": "1.250", "note": "test"}
    assert "supplier_id" not in result


def test_issue_note_optional():
    assert StockOutflowView._build_payload(177, "1", " ", kind="issue")["note"] is None


def test_writeoff_reason_required():
    with pytest.raises(ValueError, match="причину"):
        StockOutflowView._build_payload(177, "1", " ", kind="writeoff")


@pytest.mark.parametrize("quantity", ["", "0", "-1", "NaN", "Infinity", "1.0001", "abc"])
def test_bad_quantities(quantity):
    with pytest.raises(ValueError):
        StockOutflowView._build_payload(177, quantity, "Причина", kind="writeoff")


@pytest.mark.parametrize("product_id", [0, -1, True, "177"])
def test_bad_product_ids(product_id):
    with pytest.raises(ValueError):
        StockOutflowView._build_payload(product_id, "1", "Причина", kind="writeoff")


def test_bad_kind():
    with pytest.raises(ValueError):
        StockOutflowView._build_payload(177, "1", "Причина", kind="receipt")


def test_product_pagination():
    class FakeProducts:
        calls = []
        def list_products(self, offset, limit):
            self.calls.append((offset, limit))
            return [{"id": i} for i in range(100)] if offset == 0 else [{"id": 101}]
    service = FakeProducts()
    result = StockOutflowView._all_products(service)
    assert len(result) == 101
    assert service.calls == [(0, 100), (100, 100)]
