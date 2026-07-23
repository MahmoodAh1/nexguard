"""Unit tests for env-driven settings."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from nexguard.config.settings import Settings

STRONG_SECRET = "kJ8x2Qp7vRm4Tz9Lw3Nc6Yb1Ha5Gd0Fe8Su2Wi4Oq"


def _settings(**overrides: object) -> Settings:
    # _env_file=None keeps the test hermetic (ignores any local .env).
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_defaults_are_sane() -> None:
    settings = _settings()
    assert settings.env == "development"
    assert settings.event_bus == "memory"
    assert settings.llm_provider == "stub"
    assert 0.0 <= settings.alert_threshold <= 1.0


def test_cors_origins_split() -> None:
    settings = _settings(cors_origins="http://a.com, http://b.com ,")
    assert settings.cors_origin_list == ["http://a.com", "http://b.com"]


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(ValidationError):
        _settings(log_level="LOUD")


def test_production_rejects_insecure_secret() -> None:
    with pytest.raises(ValidationError):
        _settings(env="production", jwt_secret=SecretStr("change-me-in-development-only"))


def test_production_accepts_strong_secret() -> None:
    settings = _settings(env="production", jwt_secret=SecretStr(STRONG_SECRET))
    assert settings.is_production is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("postgres://u:p@h:5432/db", "postgresql+asyncpg://u:p@h:5432/db"),
        ("postgresql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
        ("sqlite+aiosqlite:///./x.db", "sqlite+aiosqlite:///./x.db"),
        ("postgresql+asyncpg://u:p@h/db", "postgresql+asyncpg://u:p@h/db"),
    ],
)
def test_database_url_is_normalized_for_async_driver(raw: str, expected: str) -> None:
    assert _settings(database_url=raw).database_url == expected
