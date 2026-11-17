from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    APP_NAME: str = "Customer Audience Engine"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    # Database Configuration
    DATABASE_URL: str = "sqlite:///./customer_engine.db"
    TEST_DATABASE_URL: str = "sqlite:///:memory:"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Returns a cached instance of application settings."""
    return Settings()
