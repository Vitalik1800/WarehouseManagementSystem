from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    unit: str = Field(
        default="pcs",
        min_length=1,
        max_length=20
    )
    description: str | None = None

    category_id: int = Field(gt=0)
    location_id: int = Field(gt=0)

    @field_validator("sku", "name", "unit", mode="before")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("Value must be a string")

        value = value.strip()

        if not value:
            raise ValueError("Value must not be blank")

        return value

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(
        cls,
        value: str | None
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("Description must be a string")

        return value.strip()


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sku: str | None = Field(
        default=None,
        min_length=1,
        max_length=64
    )
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200
    )
    unit: str | None = Field(
        default=None,
        min_length=1,
        max_length=20
    )
    description: str | None = None

    category_id: int | None = Field(
        default=None,
        gt=0
    )
    location_id: int | None = Field(
        default=None,
        gt=0
    )

    @field_validator("sku", "name", "unit", mode="before")
    @classmethod
    def validate_required_text(
        cls,
        value: str | None
    ) -> str:
        if value is None:
            raise ValueError("Field cannot be null")

        if not isinstance(value, str):
            raise ValueError("Value must be a string")

        value = value.strip()

        if not value:
            raise ValueError("Value must not be blank")

        return value

    @field_validator(
        "category_id",
        "location_id",
        mode="before"
    )
    @classmethod
    def validate_required_reference(
        cls,
        value: int | None
    ) -> int:
        if value is None:
            raise ValueError("Reference cannot be null")

        return value

    @field_validator("description", mode="before")
    @classmethod
    def validate_description(
        cls,
        value: str | None
    ) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("Description must be a string")

        return value.strip()


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sku: str
    name: str
    unit: str
    quantity: Decimal
    description: str | None
    category_id: int
    location_id: int
