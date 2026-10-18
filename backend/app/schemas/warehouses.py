from pydantic import BaseModel, ConfigDict, Field, field_validator


class WarehouseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=30)
    description: str | None = None
    is_active: bool = True

    @field_validator("name", "code", mode="before")
    @classmethod
    def normalize_required(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Value must be a nonblank string")
        return value.strip()


class WarehouseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=30)
    description: str | None = None
    is_active: bool | None = None

    @field_validator("name", "code", mode="before")
    @classmethod
    def normalize_required(cls, value: str | None) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Value must be a nonblank string")
        return value.strip()

    @field_validator("is_active")
    @classmethod
    def validate_active(cls, value: bool | None) -> bool:
        if value is None:
            raise ValueError("is_active cannot be null")
        return value


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    description: str | None
    is_active: bool
