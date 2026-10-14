
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class StockBalanceResponse(BaseModel):
    """Response schema for a product's current stock balance."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(gt=0)
    sku: str
    name: str
    unit: str
    quantity: Decimal = Field(
        allow_inf_nan=False,
        max_digits=14,
        decimal_places=3
    )
    category_id: int = Field(gt=0),
    location_id: int = Field(gt=0)
