from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    """Дані для створення користувача адміністратором."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=2,
        max_length=150
    )

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$"
    )

    password: str = Field(
        min_length=8,
        max_length=128
    )

    role: Literal["admin", "worker"] = "worker"

    @field_validator("name", "username", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class UserUpdate(BaseModel):

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150
    )

    username: str | None = Field(
        default=None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$"
    )

    @field_validator("name", "username", mode="before")
    @classmethod
    def validate_not_null(cls, value: str) -> str:
        if value is None:
            raise ValueError("Field cannot be null")

        return value

    @field_validator("name", "username")
    @classmethod
    def validate_not_blank(
        cls,
        value: str | None
    ) -> str | None:
        if value is None:
            return None

        value = value.strip()

        if not value:
            raise ValueError("Field must not be blank")

        return value


class UserRoleUpdate(BaseModel):
    role: Literal["admin", "worker"]


class UserStatusUpdate(BaseModel):
    is_active: bool
