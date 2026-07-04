"""Synthetic ground-truth profile.

This table exists **only for synthetic data**. It stores the true latent feature
vector and the sampled default outcome that the data generator used, so the
Stage 3 model has training labels and tests can validate the data-generating
process. It is deliberately separate from the production tables (and named
``synthetic_*``) so synthetic data is never confused with real records.

In production this table is simply empty — real default outcomes are observed
through repayment behaviour, not seeded.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, String, false
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SyntheticCustomerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Generator ground truth for one synthetic customer."""

    __tablename__ = "synthetic_customer_profile"

    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # The true outcome we predict (sampled with irreducible noise).
    default_label: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # The best a feature-using model could achieve (noise-free signal pd).
    default_probability_true: Mapped[float] = mapped_column(Float, nullable=False)
    # The true latent Appendix A features used to generate the raw data.
    latent_features_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    scenario: Mapped[str | None] = mapped_column(String(64), nullable=True)
