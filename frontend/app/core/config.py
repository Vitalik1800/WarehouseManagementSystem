from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class FrontendSettings(BaseSettings):
    frontend_api_base_url: str = (
        "http://127.0.0.1:8000"
    )
    frontend_request_timeout: float = Field(
        default=10.0,
        gt=0
    )

    frontend_appearance_mode: Literal[
        "System", "Light", "Dark"
    ] = "System"

    frontend_color_theme: Literal[
        "blue", "green", "dark-blue"
    ] = "blue"

    frontend_window_width: int = Field(
        default=1100,
        ge=800
    )
    frontend_window_height: int = Field(
        default=700,
        ge=500
    )

    frontend_min_window_width: int = Field(
        default=800,
        ge=400
    )
    frontend_min_window_height: int = Field(
        default=500,
        ge=300
    )

    @model_validator(mode="after")
    def validate_window_dimensions(self):
        if (
            self.frontend_window_width
            < self.frontend_min_window_width
        ):
            raise ValueError(
                "Window width cannot be smaller "
                "than minimum window width"
            )

        if (
            self.frontend_window_height
            < self.frontend_min_window_height
        ):
            raise ValueError(
                "Window height cannot be smaller "
                "than minimum window height"
            )

        return self

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False
    )


@lru_cache
def get_frontend_settings() -> FrontendSettings:
    return FrontendSettings()
