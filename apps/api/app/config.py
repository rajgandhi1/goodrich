from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_API_DIR = Path(__file__).resolve().parents[1]
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env", override=False)
load_dotenv(_API_DIR / ".env", override=False)


class Settings(BaseSettings):
    app_name: str = "GGPL Gasket Quote API"
    environment: str = Field(default="local", alias="APP_ENV")
    api_version: str = "0.1.0"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_enabled: bool = Field(default=False, alias="REDIS_ENABLED")
    approved_quote_redis_enabled: bool = Field(default=False, alias="APPROVED_QUOTE_REDIS_ENABLED")
    extraction_backend: str = Field(default="local", alias="EXTRACTION_BACKEND")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/gasket_quote",
        alias="DATABASE_URL",
    )
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")
    posthog_api_key: str | None = Field(default=None, alias="POSTHOG_API_KEY")
    posthog_host: str = Field(default="https://app.posthog.com", alias="POSTHOG_HOST")
    microsoft_tenant_id: str | None = Field(default=None, alias="MICROSOFT_TENANT_ID")
    microsoft_client_id: str | None = Field(default=None, alias="MICROSOFT_CLIENT_ID")
    microsoft_client_secret: str | None = Field(default=None, alias="MICROSOFT_CLIENT_SECRET")
    outlook_default_mailbox: str | None = Field(default=None, alias="OUTLOOK_DEFAULT_MAILBOX")
    auth_secret: str = Field(default="dev-only-change-me", alias="AUTH_SECRET")
    auth_cookie_name: str = Field(default="ggpl_session", alias="AUTH_COOKIE_NAME")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
