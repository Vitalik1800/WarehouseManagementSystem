from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


class StorageLocationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError(
                "Storage location name must be a string"
            )

        value = value.strip()

        if not value:
            raise ValueError(
                "Storage location name must not be blank"
            )

        return value


class StorageLocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100
    )
    description: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError(
                "Storage location name cannot be null"
            )

        if not isinstance(value, str):
            raise ValueError(
                "Storage location name must be a string"
            )

        value = value.strip()

        if not value:
            raise ValueError(
                "Storage location name must not be blank"
            )

        return value


class StorageLocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
