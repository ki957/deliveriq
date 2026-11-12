"""Application settings. The only place that reads environment variables (CODE_STRUCTURE §7)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

AppEnv = Literal["local", "test", "production"]


class Settings(BaseSettings):
    """Validated at startup; a missing or invalid value fails fast, naming the key only."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", frozen=True)

    app_env: AppEnv = Field(validation_alias="APP_ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    db_host: str = Field(validation_alias="DB_HOST")
    db_port: int = Field(default=5432, validation_alias="DB_PORT")
    db_name: str = Field(validation_alias="POSTGRES_DB")
    db_user: str = Field(validation_alias="DB_USER")
    db_password: SecretStr = Field(validation_alias="DB_PASSWORD")

    redis_url: SecretStr = Field(validation_alias="REDIS_URL")

    @property
    def database_url(self) -> URL:
        # URL.create escapes special characters in the password.
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def is_local_or_test(self) -> bool:
        return self.app_env in ("local", "test")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
