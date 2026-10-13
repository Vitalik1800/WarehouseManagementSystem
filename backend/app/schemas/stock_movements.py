from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator
)


MovementType = Literal["receipt", "issue", "writeoff"]


class StockMovementCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    movement_type: MovementType

    quantity: Decimal = Field(
        gt=Decimal("0"),
        max_digits=14,
        decimal_places=3,
        allow_inf_nan=False
    )

    supplier_id: int | None = Field(
        default=None,
        gt=0
    )

    note: str | None = None

    @field_validator("product_id", "supplier_id", mode="before")
    @classmethod
    def validate_identifiers(cls, value):
        if value is None:
            return None

        if isinstance(value, bool):
            raise ValueError("Identifier must be an integer")

        return value

    @field_validator("quantity", mode="before")
    @classmethod
    def validate_quantity(cls, value):
        if isinstance(value, bool):
            raise ValueError("Quantity must be numeric")

        return value

    @field_validator("note", mode="before")
    @classmethod
    def validate_note(
        cls,
        value: str | None
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("Note must be a string")

        value = value.strip()

        return value or None

    @model_validator(mode="after")
    def validate_movement_rules(self):
        if self.movement_type == "writeoff" and not self.note:
            raise ValueError(
                "Writeoff requires a reason in note"
            )

        if (
            self.movement_type != "receipt"
            and self.supplier_id is not None
        ):
            raise ValueError(
                "Supplier is allowed only for receipts"
            )

        return self


class StockMovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    user_id: int
    supplier_id: int | None

    movement_type: MovementType
    quantity: Decimal
    created_at: datetime
    note: str | None


class StockBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    sku: str
    name: str
    unit: str
    quantity: Decimal
