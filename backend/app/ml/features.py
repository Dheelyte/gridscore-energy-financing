"""Deterministic feature engineering: raw events/signals → feature vector.

The **same** code path produces features for training (over the generated
population) and for inference (over rows read from the database). It supports the
two cooperative views:

* ``SOLO``   — only the home operator's repayment events are visible.
* ``POOLED`` — the full cooperative repayment history is visible.

Enrichment signals (mobile-money, airtime, utility) are customer-level and shared
by both views, so the cooperative network effect comes specifically from pooling
**repayment history** — exactly the product thesis.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import ProviderType, RepaymentStatus, ScoreView
from app.ml.feature_schema import FEATURE_NAMES


@dataclass(frozen=True)
class EventRecord:
    """A view-agnostic repayment event (adapts both generated and DB rows)."""

    operator_key: str
    due_date: dt.date
    paid_date: dt.date | None
    status: RepaymentStatus
    instalment_amount: Decimal


@dataclass(frozen=True)
class RawCustomerData:
    """Everything needed to build a feature vector for one customer."""

    home_operator_key: str
    events: list[EventRecord]
    signals: dict[ProviderType, dict[str, float]]  # latest payload per provider


def _months_between(start: dt.date, end: dt.date) -> int:
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


class FeatureExtractor:
    """Builds the canonical nine-feature vector from raw customer data."""

    def extract(
        self,
        raw: RawCustomerData,
        view: ScoreView,
        *,
        reference_date: dt.date,
    ) -> dict[str, float]:
        events = (
            raw.events
            if view is ScoreView.POOLED
            else [e for e in raw.events if e.operator_key == raw.home_operator_key]
        )
        repayment = self._repayment_features(events, reference_date)
        enrichment = self._enrichment_features(raw.signals)

        loan_to_income = 0.0
        inflow = enrichment["mm_avg_monthly_inflow_usd"]
        if inflow > 0 and events:
            mean_instalment = float(sum(e.instalment_amount for e in events) / len(events))
            loan_to_income = mean_instalment / inflow

        features = {**repayment, **enrichment, "loan_to_income": loan_to_income}
        # Return in canonical order.
        return {name: float(features[name]) for name in FEATURE_NAMES}

    def _repayment_features(
        self, events: list[EventRecord], reference_date: dt.date
    ) -> dict[str, float]:
        n = len(events)
        if n == 0:
            # No visible history — maximally uncertain; the model reads this as
            # thin-file risk (and is exactly when the pooled view adds value).
            return {
                "payg_repayment_rate": 0.0,
                "payg_history_months": 0.0,
                "prior_defaults": 0.0,
                "tenure_months": 0.0,
            }
        on_time = sum(1 for e in events if e.status is RepaymentStatus.ON_TIME)
        defaults = sum(1 for e in events if e.status is RepaymentStatus.DEFAULTED)
        months = {(e.due_date.year, e.due_date.month) for e in events}
        earliest = min(e.due_date for e in events)
        return {
            "payg_repayment_rate": on_time / n,
            "payg_history_months": float(len(months)),
            "prior_defaults": float(defaults),
            "tenure_months": float(_months_between(earliest, reference_date)),
        }

    def _enrichment_features(
        self, signals: dict[ProviderType, dict[str, float]]
    ) -> dict[str, float]:
        mm = signals.get(ProviderType.MOBILE_MONEY, {})
        airtime = signals.get(ProviderType.AIRTIME, {})
        utility = signals.get(ProviderType.UTILITY, {})
        return {
            "mm_inflow_stability": float(mm.get("inflow_stability", 0.0)),
            "mm_avg_monthly_inflow_usd": float(mm.get("avg_monthly_inflow_usd", 0.0)),
            "airtime_topup_regularity": float(airtime.get("topup_regularity", 0.0)),
            "utility_payment_score": float(utility.get("payment_score", 0.0)),
        }
