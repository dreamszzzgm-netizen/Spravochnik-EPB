from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Spravoshnik EPB"
    app_version: str = "0.1.0"

    database_url: str = Field(
        default="postgresql+psycopg://spravoshnik:spravoshnik@localhost:5432/spravoshnik"
    )
    test_database_url: str | None = None

    storage_root: Path = Path("./var/storage")
    log_level: str = "INFO"

    worker_poll_interval_seconds: float = Field(default=2.0, gt=0)
    scheduler_tick_seconds: float = Field(default=30.0, gt=0)

    session_absolute_timeout_minutes: int = Field(default=720, ge=5, le=10080)
    session_inactivity_timeout_minutes: int = Field(default=60, ge=5, le=1440)
    failed_login_limit: int = Field(default=5, ge=1, le=20)
    failed_login_lock_minutes: int = Field(default=15, ge=1, le=1440)
    session_cookie_name: str = "spravoshnik_session"
    session_cookie_secure: bool = False

    @property
    def effective_database_url(self) -> str:
        if self.app_env == "test" and self.test_database_url:
            return self.test_database_url
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
