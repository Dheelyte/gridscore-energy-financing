"""Property-based tests for the score transform (Hypothesis)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.services.scoring.transform import (
    SCORE_MAX,
    SCORE_MIN,
    TIER_CUTOFFS,
    pd_to_score,
    pd_to_tier,
)

pytestmark = pytest.mark.unit

_pd = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)


@given(_pd)
def test_score_always_in_range(pd: float) -> None:
    assert SCORE_MIN <= pd_to_score(pd) <= SCORE_MAX


@given(_pd, _pd)
def test_score_is_monotonic_non_increasing(a: float, b: float) -> None:
    lo, hi = sorted((a, b))
    # Lower PD must never score lower than higher PD.
    assert pd_to_score(lo) >= pd_to_score(hi)


@given(_pd)
def test_tier_is_consistent_with_cutoffs(pd: float) -> None:
    tier = pd_to_tier(pd)
    # The tier's lower bound is the previous cutoff; its upper bound is its own.
    bounds = dict(TIER_CUTOFFS)
    assert pd < bounds[tier]


@given(_pd, _pd)
def test_worse_pd_never_improves_tier(a: float, b: float) -> None:
    lo, hi = sorted((a, b))
    order = [t for t, _ in TIER_CUTOFFS]
    # A lower PD lands in an equal-or-better (earlier) tier.
    assert order.index(pd_to_tier(lo)) <= order.index(pd_to_tier(hi))
