from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator
)


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    contact_person: str | None = Field(
        default=None,
        max_length=150
    )
    phone: str | None = Field(
        default=None,
        max_length=30
    )
    email: EmailStr | None = None
    address: str | None = None

    @field_validator(
        "name",
        "contact_person",
        "phone",
        "email",
        "address",
        mode="before"
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("Field must be a string")

        return value.strip()

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Supplier name must not be blank")

        return value


class SupplierUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=150
    )
    contact_person: str | None = Field(
        default=None,
        max_length=150
    )
    phone: str | None = Field(
        default=None,
        max_length=30
    )
    email: EmailStr | None = None
    address: str | None = None

    @field_validator(
        "name",
        "contact_person",
        "phone",
        "email",
        "address",
        mode="before"
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError("Field must be a string")

        return value.strip()

    @field_validator("name", mode="before")
    @classmethod
    def validate_name_not_null(
        cls,
        value: str | None
    ) -> str:
        if value is None:
            raise ValueError("Supplier name cannot be null")

        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("Supplier name must not be blank")

        return value


class SupplierResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
