from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Always resolve .env from apps/api, regardless of process CWD.
_API_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _API_ROOT / ".env"


class Settings(BaseSettings):
    """Environment-based configuration. Secrets come from env / .env only."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "EVALSURE"
    api_prefix: str = "/api/v1"
    debug: bool = False
    environment: str = "development"

    # Async SQLAlchemy (app) and sync (Alembic). Local defaults match README / .env.example.
    database_url: str = Field(
        default="postgresql+asyncpg://evalsure:evalsure@localhost:5432/evalsure",
        description="Async database URL",
    )
    database_url_sync: str = Field(
        default="postgresql://evalsure:evalsure@localhost:5432/evalsure",
        description="Sync database URL for Alembic",
    )

    # Required — set via JWT_SECRET in environment or apps/api/.env (never commit real values).
    jwt_secret: str = Field(min_length=16)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7


@lru_cache
def get_settings() -> Settings:
    return Settings()
