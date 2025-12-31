"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Strava configuration
    strava_client_id: str = Field(alias="CLIENT_ID")
    strava_client_secret: str = Field(alias="CLIENT_SECRET")
    strava_refresh_token: str | None = Field(default=None, alias="STRAVA_REFRESH_TOKEN")

    # Notion configuration
    notion_token: str = Field(alias="TOKEN_V3")
    notion_database_id: str = Field(alias="DATABASE_ID")

    # Sync configuration
    rate_limit_delay: float = Field(default=0.35, description="Seconds between Notion API calls")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]
