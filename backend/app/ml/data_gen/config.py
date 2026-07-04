"""Configuration for the synthetic data engine.

The default coefficients encode the **product thesis** (Appendix A): repayment
behaviour and prior defaults dominate the default-generating process, with
supporting signals from mobile-money, airtime, and utility data. Coefficients
act on *standardised* features, so their magnitudes are directly comparable and
the sign matches the documented direction.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperatorSpec:
    """A synthetic PAYG operator (tenant) in the cooperative."""

    name: str
    country: str  # ISO 3166-1 alpha-2
    currency: str  # ISO 4217 (informational; synthetic amounts are USD-equivalent)


# A curated, recognisable roster of Sub-Saharan PAYG operators (all synthetic).
DEFAULT_OPERATORS: tuple[OperatorSpec, ...] = (
    OperatorSpec("Helios Energy", "KE", "KES"),
    OperatorSpec("SolarNova", "NG", "NGN"),
    OperatorSpec("PowaPay Solar", "UG", "UGX"),
    OperatorSpec("Jua Power", "TZ", "TZS"),
    OperatorSpec("Sahel Light", "GH", "GHS"),
)

# Logistic coefficients on standardised features (sign = Appendix A direction,
# magnitude = strength). PAYG repayment rate and prior defaults are the strongest
# — this ordering *is* the product thesis and Stage 3's model must recover it.
DEFAULT_COEFFICIENTS: dict[str, float] = {
    "payg_repayment_rate": -1.65,  # strong protective
    "prior_defaults": 1.45,  # strong risk
    "loan_to_income": 1.05,  # strong risk
    "mm_inflow_stability": -0.70,
    "utility_payment_score": -0.55,
    "airtime_topup_regularity": -0.50,
    "payg_history_months": -0.40,
    "tenure_months": -0.30,
    "mm_avg_monthly_inflow_usd": -0.30,  # mild protective
}


@dataclass(frozen=True)
class GeneratorConfig:
    """Knobs for a generation run. Defaults yield a credible cooperative."""

    seed: int = 20260620
    n_customers: int = 2000
    operators: tuple[OperatorSpec, ...] = DEFAULT_OPERATORS

    # Target base default rate (Appendix A: ~10-20%). The intercept is calibrated
    # to hit this on the generated population.
    target_default_rate: float = 0.15

    # The coefficients above are written at interpretable "thesis strength"; on
    # their own the nine correlated features make the population almost perfectly
    # separable. ``signal_scale`` shrinks the combined signal so the achievable
    # (Bayes) AUC is realistic (~0.80) and the Stage 3 model lands at ~0.75-0.80.
    signal_scale: float = 0.26

    # Irreducible noise added to the *label* logit (invisible to the features).
    # Together with signal_scale this caps the achievable AUC.
    logit_noise_sd: float = 1.0

    coefficients: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_COEFFICIENTS))

    # The most recent instalment due-month anchors all generated histories. Kept
    # inside the migration's partition window (2023-2026).
    anchor_month: dt.date = dt.date(2026, 5, 1)

    # Fraction of customers who also have repayment history at operators other
    # than their home operator — i.e. customers for whom the cooperative adds
    # information (the pooled view differs from the solo view).
    cross_operator_fraction: float = 0.55

    # Share of customers missing scoring consent (exercises consent gating later).
    no_consent_fraction: float = 0.08

    @property
    def n_operators(self) -> int:
        return len(self.operators)
