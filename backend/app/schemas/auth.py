from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


class UserRegister(BaseModel):
    name: str = Field(
        min_length=2,
        max_length=150,
        description="Повне ім'я користувача"
    )

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="Логін із латинських літер, цифр і підкреслень"
    )

    password: str = Field(
        min_length=8,
        max_length=128,
        description="Пароль користувача"
    )

    @field_validator("name", "username")
    @classmethod
    def validate_not_blank(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Поле не може бути порожнім")

        return value


class UserLogin(BaseModel):
    username: str = Field(
        min_length=1,
        max_length=50
    )

    password: str = Field(
        min_length=1
    )


class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    role: Literal["admin", "worker"]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
