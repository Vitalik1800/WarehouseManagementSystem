from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator
)


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
    refresh_token: str | None = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=512)


class LogoutRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1, max_length=512)
