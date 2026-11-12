"""Application settings. The only place that reads environment variables (CODE_STRUCTURE §7)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

AppEnv = Literal["local", "test", "production"]
# MOCK_OTP is local/test only (#15 §4.2, DDR-96). No SMS provider exists in the POC (DDR-40),
# so production runs with "disabled": OTP requests fail closed with a clear error.
OtpAdapter = Literal["mock", "disabled"]


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

    otp_adapter: OtpAdapter = Field(default="disabled", validation_alias="OTP_ADAPTER")
    otp_pepper: SecretStr = Field(validation_alias="OTP_PEPPER", min_length=16)
    # Comma-separated dev origins allowed for cross-origin requests (DDR-98). Empty = none.
    cors_origins: str = Field(default="", validation_alias="CORS_ORIGINS")

    @model_validator(mode="after")
    def _mock_otp_only_outside_production(self) -> Settings:
        if self.otp_adapter == "mock" and not self.is_local_or_test:
            raise ValueError("OTP_ADAPTER=mock is allowed only when APP_ENV is local or test")
        return self

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

    @property
    def secure_cookies(self) -> bool:
        # Local and test run over plain HTTP on 127.0.0.1; production cookies are always Secure.
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
