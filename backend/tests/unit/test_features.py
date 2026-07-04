"""Feature-engineering tests: solo vs pooled correctness (no ML libs needed)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from app.domain.enums import ProviderType, RepaymentStatus, ScoreView
from app.ml.features import EventRecord, FeatureExtractor, RawCustomerData

pytestmark = pytest.mark.unit

_REF = dt.date(2026, 6, 1)


def _event(op: str, month: int, status: RepaymentStatus, amount: str = "20.00") -> EventRecord:
    return EventRecord(
        operator_key=op,
        due_date=dt.date(2025, month, 5),
        paid_date=(dt.date(2025, month, 5) if status is RepaymentStatus.ON_TIME else None),
        status=status,
        instalment_amount=Decimal(amount),
    )


def _signals() -> dict[ProviderType, dict[str, float]]:
    return {
        ProviderType.MOBILE_MONEY: {
            "avg_monthly_inflow_usd": 200.0,
            "inflow_stability": 0.8,
        },
        ProviderType.AIRTIME: {"topup_regularity": 0.7},
        ProviderType.UTILITY: {"payment_score": 0.75},
    }


def test_pooled_uses_all_events_solo_uses_home_only() -> None:
    raw = RawCustomerData(
        home_operator_key="home",
        events=[
            _event("home", 1, RepaymentStatus.LATE),
            _event("home", 2, RepaymentStatus.ON_TIME),
            _event("other", 3, RepaymentStatus.ON_TIME),
            _event("other", 4, RepaymentStatus.ON_TIME),
        ],
        signals=_signals(),
    )
    ex = FeatureExtractor()
    solo = ex.extract(raw, ScoreView.SOLO, reference_date=_REF)
    pooled = ex.extract(raw, ScoreView.POOLED, reference_date=_REF)

    # Solo sees 2 home events (1 on-time); pooled sees 4 (3 on-time).
    assert solo["payg_history_months"] == 2
    assert pooled["payg_history_months"] == 4
    assert solo["payg_repayment_rate"] == pytest.approx(0.5)
    assert pooled["payg_repayment_rate"] == pytest.approx(0.75)
    # The pooled view looks materially better — the network effect in features.
    assert pooled["payg_repayment_rate"] > solo["payg_repayment_rate"]


def test_enrichment_is_shared_across_views() -> None:
    raw = RawCustomerData("home", [_event("home", 1, RepaymentStatus.ON_TIME)], _signals())
    ex = FeatureExtractor()
    solo = ex.extract(raw, ScoreView.SOLO, reference_date=_REF)
    pooled = ex.extract(raw, ScoreView.POOLED, reference_date=_REF)
    for key in (
        "mm_inflow_stability",
        "mm_avg_monthly_inflow_usd",
        "utility_payment_score",
    ):
        assert solo[key] == pooled[key]


def test_prior_defaults_and_loan_to_income() -> None:
    raw = RawCustomerData(
        home_operator_key="home",
        events=[
            _event("home", 1, RepaymentStatus.DEFAULTED, "50.00"),
            _event("home", 2, RepaymentStatus.ON_TIME, "50.00"),
        ],
        signals=_signals(),
    )
    feats = FeatureExtractor().extract(raw, ScoreView.POOLED, reference_date=_REF)
    assert feats["prior_defaults"] == 1
    # mean instalment 50 / inflow 200 = 0.25
    assert feats["loan_to_income"] == pytest.approx(0.25)


def test_empty_solo_view_is_thin_file() -> None:
    raw = RawCustomerData("home", [_event("other", 1, RepaymentStatus.ON_TIME)], _signals())
    feats = FeatureExtractor().extract(raw, ScoreView.SOLO, reference_date=_REF)
    assert feats["payg_history_months"] == 0
    assert feats["payg_repayment_rate"] == 0.0
    assert feats["prior_defaults"] == 0
    # Enrichment still available even with no repayment history.
    assert feats["mm_inflow_stability"] == 0.8
