"""The PD -> Energy Credit Score transform and risk tiers."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.enums import RiskTier
from app.services.scoring.transform import (
    SCORE_MAX,
    SCORE_MIN,
    is_approved,
    pd_to_score,
    pd_to_tier,
)

pytestmark = pytest.mark.unit


def test_score_is_monotonic_decreasing_in_pd() -> None:
    grid = np.linspace(0.0, 1.0, 500)
    scores = [pd_to_score(float(p)) for p in grid]
    assert all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))


def test_score_stays_within_bounds_even_at_extremes() -> None:
    for p in (0.0, 1e-9, 0.5, 1.0 - 1e-9, 1.0):
        assert SCORE_MIN <= pd_to_score(p) <= SCORE_MAX


def test_lower_pd_scores_strictly_higher() -> None:
    assert pd_to_score(0.02) > pd_to_score(0.15) > pd_to_score(0.5)


@pytest.mark.parametrize(
    ("pd", "tier"),
    [
        (0.01, RiskTier.A),
        (0.049, RiskTier.A),
        (0.05, RiskTier.B),
        (0.099, RiskTier.B),
        (0.10, RiskTier.C),
        (0.19, RiskTier.C),
        (0.20, RiskTier.D),
        (0.34, RiskTier.D),
        (0.35, RiskTier.E),
        (0.9, RiskTier.E),
    ],
)
def test_risk_tier_cutoffs(pd: float, tier: RiskTier) -> None:
    assert pd_to_tier(pd) is tier


def test_decision_threshold() -> None:
    assert is_approved(0.10, 0.25) is True
    assert is_approved(0.25, 0.25) is False
    assert is_approved(0.40, 0.25) is False
