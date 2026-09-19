from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
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

    # Required — set via EVALSURE_JWT_SECRET / JWT_SECRET (never commit real values).
    jwt_secret: str = Field(
        min_length=16,
        validation_alias=AliasChoices("EVALSURE_JWT_SECRET", "JWT_SECRET"),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        validation_alias=AliasChoices("EVALSURE_JWT_ALGORITHM", "JWT_ALGORITHM"),
    )
    jwt_expire_minutes: int = Field(
        default=60 * 24 * 7,
        validation_alias=AliasChoices(
            "EVALSURE_ACCESS_TOKEN_EXPIRE_MINUTES",
            "JWT_EXPIRE_MINUTES",
        ),
    )

    # Comma-separated browser origins for the dashboard (intentional CORS, not "*").
    cors_origins: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("EVALSURE_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    # LLM-as-a-judge (secrets never logged or persisted).
    judge_provider: str = Field(
        default="openai_compatible",
        validation_alias=AliasChoices("EVALSURE_JUDGE_PROVIDER", "JUDGE_PROVIDER"),
    )
    judge_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("EVALSURE_JUDGE_MODEL", "JUDGE_MODEL"),
    )
    judge_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("EVALSURE_JUDGE_API_KEY", "JUDGE_API_KEY"),
    )
    judge_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("EVALSURE_JUDGE_BASE_URL", "JUDGE_BASE_URL"),
    )
    judge_timeout_seconds: float = Field(
        default=60.0,
        validation_alias=AliasChoices("EVALSURE_JUDGE_TIMEOUT_SECONDS", "JUDGE_TIMEOUT_SECONDS"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
