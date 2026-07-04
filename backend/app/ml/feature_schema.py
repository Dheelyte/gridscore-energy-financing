"""Canonical feature schema (Appendix A).

The single source of truth for the model's feature vocabulary: names, human
labels, valid ranges, and the *direction* each feature pushes default risk.

This is shared across the codebase so the synthetic data engine (Stage 2), the
feature-engineering pipeline (Stage 3), the explanations UI, and the model card
all speak the same language. All nine features are computable from
``repayment_event`` + ``enrichment_signal``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Direction(StrEnum):
    """Sign of a feature's association with default probability."""

    INCREASES = "increases"  # higher value => higher default risk
    DECREASES = "decreases"  # higher value => lower default risk


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    label: str  # human-readable, for the "top factors" UI
    direction: Direction
    strength: str  # qualitative magnitude from Appendix A: strong | medium | mild
    min_value: float
    max_value: float
    description: str


# Order is the canonical feature-vector order used everywhere downstream.
FEATURES: tuple[FeatureSpec, ...] = (
    FeatureSpec(
        "payg_repayment_rate",
        "PAYG on-time repayment rate",
        Direction.DECREASES,
        "strong",
        0.0,
        1.0,
        "Share of PAYG instalments paid on time.",
    ),
    FeatureSpec(
        "payg_history_months",
        "Length of PAYG history",
        Direction.DECREASES,
        "medium",
        0.0,
        60.0,
        "Months of observed PAYG repayment history.",
    ),
    FeatureSpec(
        "mm_inflow_stability",
        "Mobile-money inflow stability",
        Direction.DECREASES,
        "medium",
        0.0,
        1.0,
        "Stability (low volatility) of mobile-money inflows.",
    ),
    FeatureSpec(
        "mm_avg_monthly_inflow_usd",
        "Average monthly mobile-money inflow",
        Direction.DECREASES,
        "mild",
        0.0,
        5000.0,
        "Average monthly mobile-money inflow in USD.",
    ),
    FeatureSpec(
        "airtime_topup_regularity",
        "Airtime top-up regularity",
        Direction.DECREASES,
        "medium",
        0.0,
        1.0,
        "Regularity of airtime purchases.",
    ),
    FeatureSpec(
        "utility_payment_score",
        "Utility payment consistency",
        Direction.DECREASES,
        "medium",
        0.0,
        1.0,
        "Consistency of other utility/bill payments.",
    ),
    FeatureSpec(
        "loan_to_income",
        "Loan-to-income ratio",
        Direction.INCREASES,
        "strong",
        0.0,
        2.0,
        "Instalment amount divided by monthly inflow.",
    ),
    FeatureSpec(
        "prior_defaults",
        "Prior defaults on record",
        Direction.INCREASES,
        "strong",
        0.0,
        10.0,
        "Count of prior defaults visible in the cooperative.",
    ),
    FeatureSpec(
        "tenure_months",
        "Customer tenure",
        Direction.DECREASES,
        "mild",
        0.0,
        60.0,
        "Months as an identifiable customer.",
    ),
)

FEATURE_NAMES: tuple[str, ...] = tuple(f.name for f in FEATURES)
FEATURE_BY_NAME: dict[str, FeatureSpec] = {f.name: f for f in FEATURES}
