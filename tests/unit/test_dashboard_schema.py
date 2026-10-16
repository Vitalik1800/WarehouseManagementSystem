import pytest

from pydantic import ValidationError

from backend.app.schemas.dashboard import DashboardSummaryResponse


@pytest.fixture
def valid_summary():
    return {
        "total_products": 100,
        "total_categories": 8,
        "total_suppliers": 12,
        "total_locations": 3,
        "in_stock_products": 85,
        "out_of_stock_products": 15
    }


def test_dashboard_summary_valid(valid_summary):
    result = DashboardSummaryResponse(**valid_summary)

    assert result.model_dump() == valid_summary


def test_dashboard_summary_accepts_zeros():
    result = DashboardSummaryResponse(
        total_products=0,
        total_categories=0,
        total_suppliers=0,
        total_locations=0,
        in_stock_products=0,
        out_of_stock_products=0
    )

    assert all(
        value == 0
        for value in result.model_dump().values()
    )


@pytest.mark.parametrize(
    "field",
    [
        "total_products",
        "total_categories",
        "total_suppliers",
        "total_locations",
        "in_stock_products",
        "out_of_stock_products"
    ]
)
def test_dashboard_summary_rejects_negative_values(
    valid_summary,
    field
):
    data = valid_summary.copy()
    data[field] = -1

    with pytest.raises(ValidationError):
        DashboardSummaryResponse(**data)


@pytest.mark.parametrize(
    "field",
    [
        "total_products",
        "total_categories",
        "total_suppliers",
        "total_locations",
        "in_stock_products",
        "out_of_stock_products"
    ]
)
def test_dashboard_summary_requires_all_fields(
    valid_summary,
    field
):
    data = valid_summary.copy()
    del data[field]

    with pytest.raises(ValidationError):
        DashboardSummaryResponse(**data)
