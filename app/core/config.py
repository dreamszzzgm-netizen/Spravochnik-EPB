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
    app_version: str = "0.0.1"

    database_url: str = Field(
        default="postgresql+psycopg://spravoshnik:spravoshnik@localhost:5432/spravoshnik"
    )
    test_database_url: str | None = None

    storage_root: Path = Path("./var/storage")
    log_level: str = "INFO"

    worker_poll_interval_seconds: float = Field(default=2.0, gt=0)
    scheduler_tick_seconds: float = Field(default=30.0, gt=0)

    @property
    def effective_database_url(self) -> str:
        if self.app_env == "test" and self.test_database_url:
            return self.test_database_url
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
