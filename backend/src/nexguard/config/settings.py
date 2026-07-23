"""Application settings, loaded from the environment (12-factor).

No secret is ever hard-coded. In production, an insecure JWT secret is rejected
at startup so a misconfiguration fails loudly rather than shipping a known key.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "production", "test"]
_INSECURE_SECRET_MARKERS = ("change-me", "insecure", "secret", "changeme")


class Settings(BaseSettings):
    """Typed, env-driven configuration."""

    model_config = SettingsConfigDict(
        env_prefix="NEXGUARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── App ──
    env: Environment = "development"
    debug: bool = True
    log_level: str = "INFO"
    log_json: bool = False

    # ── Database ──
    database_url: str = "sqlite+aiosqlite:///./nexguard.db"

    # ── Redis / event bus ──
    redis_url: str = "redis://localhost:6379/0"
    event_bus: Literal["memory", "redis"] = "memory"

    # ── Security ──
    jwt_secret: SecretStr = SecretStr("change-me-in-development-only")
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 1_209_600
    rate_limit_per_minute: int = 120
    auth_rate_limit_per_minute: int = 10

    # ── CORS ──
    cors_origins: str = "http://localhost:3000"

    # ── LLM (Ollama; local only) ──
    llm_provider: Literal["stub", "ollama"] = "stub"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    llm_timeout_seconds: float = 60.0

    # ── Detection ──
    ensemble_seq_weight: float = 0.6
    ensemble_stat_weight: float = 0.4
    alert_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    model_artifact_dir: str = "./models/artifacts"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        valid = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if level not in valid:
            raise ValueError(f"invalid log level {value!r}; expected one of {sorted(valid)}")
        return level

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        # Managed Postgres providers (Render, Railway, Heroku) hand out
        # `postgres://` / `postgresql://` URLs; SQLAlchemy's async engine needs the
        # asyncpg driver. Normalize so those URLs work out of the box.
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value

    @model_validator(mode="after")
    def _reject_insecure_production_secret(self) -> Settings:
        if self.is_production:
            secret = self.jwt_secret.get_secret_value().lower()
            if len(secret) < 32 or any(marker in secret for marker in _INSECURE_SECRET_MARKERS):
                raise ValueError(
                    "NEXGUARD_JWT_SECRET must be a strong (>=32 char) non-default secret "
                    "in production"
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton for process-wide use (tests construct directly)."""
    return Settings()
