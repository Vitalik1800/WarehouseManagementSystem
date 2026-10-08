from functools import lru_cache
from pathlib import Path

from pydantic import Field
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
