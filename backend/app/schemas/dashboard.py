from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    """Статистика головної панелі системи."""

    total_products: int = Field(ge=0)
    total_categories: int = Field(ge=0)
    total_suppliers: int = Field(ge=0)
    total_locations: int = Field(ge=0)
    in_stock_products: int = Field(ge=0)
    out_of_stock_products: int = Field(ge=0)
