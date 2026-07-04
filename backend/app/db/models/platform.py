"""Platform-level models: immutable audit log and model registry mirror."""

from __future__ import annotations

from typing import Any

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.domain.enums import PromotionStage


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only record of every score request and data access.

    Immutability is enforced at the database level by a trigger that rejects
    UPDATE and DELETE (created in the migration) — defence in depth, not just a
    convention the application promises to honour."""

    __tablename__ = "audit_log"

    actor: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class ModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A mirror of an MLflow-registered model version for in-app querying."""

    __tablename__ = "model_version"

    mlflow_run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    promoted_stage: Mapped[PromotionStage] = mapped_column(
        pg_enum(PromotionStage, "promotion_stage"),
        default=PromotionStage.NONE,
        nullable=False,
    )
