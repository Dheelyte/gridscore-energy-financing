"""Scoring artefacts: feature snapshots, score results, and cooperative lift."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, pg_enum
from app.domain.enums import RiskTier, ScoreView

if TYPE_CHECKING:
    from app.db.models.customer import Customer
    from app.db.models.tenancy import Operator


class FeatureSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A point-in-time feature vector for a customer under a given view.

    Persisting features makes scores reproducible and auditable: we can show
    exactly what the model saw. ``view`` distinguishes the solo and pooled
    feature builds that power the cooperative-lift comparison."""

    __tablename__ = "feature_snapshot"

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    features_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    view: Mapped[ScoreView] = mapped_column(pg_enum(ScoreView, "score_view"), nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="feature_snapshots")


class ScoreResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An audit-grade scoring decision: score, PD, tier, and explanation."""

    __tablename__ = "score_result"
    __table_args__ = (
        CheckConstraint(
            "energy_credit_score BETWEEN 300 AND 850",
            name="energy_credit_score_range",
        ),
        CheckConstraint(
            "default_probability BETWEEN 0 AND 1",
            name="default_probability_range",
        ),
    )

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requesting_operator_id: Mapped[UUID] = mapped_column(
        ForeignKey("operator.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    view: Mapped[ScoreView] = mapped_column(pg_enum(ScoreView, "score_view"), nullable=False)
    energy_credit_score: Mapped[int] = mapped_column(Integer, nullable=False)
    default_probability: Mapped[float] = mapped_column(Float, nullable=False)
    risk_tier: Mapped[RiskTier] = mapped_column(pg_enum(RiskTier, "risk_tier"), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="score_results")
    requesting_operator: Mapped[Operator] = relationship()


class CooperativeLift(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Materialised solo-vs-pooled comparison — the product's differentiator.

    Stores both scores and PDs plus a ``lift_metric`` so the network effect is
    queryable for analytics without recomputation."""

    __tablename__ = "cooperative_lift"

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True
    )
    solo_score: Mapped[int] = mapped_column(Integer, nullable=False)
    pooled_score: Mapped[int] = mapped_column(Integer, nullable=False)
    solo_pd: Mapped[float] = mapped_column(Float, nullable=False)
    pooled_pd: Mapped[float] = mapped_column(Float, nullable=False)
    lift_metric: Mapped[float] = mapped_column(Float, nullable=False)

    customer: Mapped[Customer] = relationship(back_populates="cooperative_lifts")
