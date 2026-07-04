"""Application settings (twelve-factor: all config from the environment).

Settings are validated once at import time and cached. Every value can be
overridden via an environment variable prefixed with ``GRIDSCORE_`` (see
``.env.example`` at the repo root). Secrets are typed as ``SecretStr`` so they
never leak into logs or ``repr`` output.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    """Deployment environment. Drives logging format and safety defaults."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Strongly-typed runtime configuration for the GridScore backend."""

    model_config = SettingsConfigDict(
        env_prefix="GRIDSCORE_",
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---- Core ----
    env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    log_json: bool = False

    # ---- API server ----
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    # ---- Security (used from later stages; declared now for a stable contract) ----
    secret_key: SecretStr = SecretStr("dev-only-change-me")
    identity_hash_salt: SecretStr = SecretStr("dev-only-identity-salt-change-me")

    # ---- Infrastructure URLs (consumed in later stages) ----
    database_url: str = "postgresql+asyncpg://gridscore:gridscore@localhost:5432/gridscore"
    redis_url: str = "redis://localhost:6379/0"
    mlflow_tracking_uri: str = "http://localhost:5000"

    # ---- Scoring (Stage 4) ----
    # Path to the serialised ScoringModel bundle produced by scripts/train_model.py.
    model_path: str = "artifacts/scoring_model.joblib"
    # Default approve/reject PD boundary. Set near the portfolio base default rate
    # (~14% on the synthetic data) so a borrower is approved only when their
    # predicted default risk is below average — the principled operating point,
    # and the one at which the borderline demo customer's solo view (PD ~0.16,
    # above average → reject) flips to approve under the pooled view (PD ~0.07).
    # 0.25 was too lax (it approved clearly above-average risk). Override per
    # deployment via GRIDSCORE_DECISION_THRESHOLD.
    decision_threshold: float = 0.12
    # Data retention (Stage 9): derived artefacts older than this are purged.
    retention_days: int = 365

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, value: object) -> object:
        """Allow CORS origins to be supplied as a comma-separated string."""
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_production(self) -> bool:
        return self.env is Environment.PRODUCTION


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached settings singleton."""
    return Settings()
