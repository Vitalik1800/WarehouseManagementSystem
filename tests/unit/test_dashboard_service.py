from unittest.mock import Mock, call

from backend.app.models.category import Category
from backend.app.models.product import Product
from backend.app.models.storage_location import StorageLocation
from backend.app.models.supplier import Supplier
from backend.app.schemas.dashboard import DashboardSummaryResponse
from backend.app.services.dashboard_service import DashboardService


def test_dashboard_summary_empty_database():
    db = Mock()
    db.scalar.return_value = 0

    service = DashboardService(db)
    result = service.get_summary()

    assert isinstance(result, DashboardSummaryResponse)

    assert result.model_dump() == {
        "total_products": 0,
        "total_categories": 0,
        "total_suppliers": 0,
        "total_locations": 0,
        "in_stock_products": 0,
        "out_of_stock_products": 0
    }

    assert db.scalar.call_count == 6


def test_dashboard_summary_with_data():
    db = Mock()
    db.scalar.side_effect = [
        100,
        8,
        12,
        3,
        85,
        15
    ]

    service = DashboardService(db)
    result = service.get_summary()

    assert result.total_products == 100
    assert result.total_categories == 8
    assert result.total_suppliers == 12
    assert result.total_locations == 3
    assert result.in_stock_products == 85
    assert result.out_of_stock_products == 15

    assert (
        result.in_stock_products + result.out_of_stock_products
        == result.total_products
    )

    assert db.scalar.call_count == 6


def test_dashboard_summary_handles_none_counts():
    db = Mock()
    db.scalar.return_value = None

    service = DashboardService(db)
    result = service.get_summary()

    assert all(
        value == 0
        for value in result.model_dump().values()
    )


def test_dashboard_summary_executes_select_queries():
    db = Mock()
    db.scalar.return_value = 0

    service = DashboardService(db)
    service.get_summary()

    statements = [
        args.args[0]
        for args in db.scalar.call_args_list
    ]

    assert len(statements) == 6

    compiled = [
        str(statement.compile()).lower()
        for statement in statements
    ]

    assert all("count(" in sql for sql in compiled)
    assert "products" in compiled[0]
    assert "categories" in compiled[1]
    assert "suppliers" in compiled[2]
    assert "storage_locations" in compiled[3]
    assert "quantity >" in compiled[4]
    assert "quantity =" in compiled[5]
