"""Map a default probability (PD) to an Energy Credit Score and a risk tier.

**Score transform.** We use the industry-standard log-odds (scorecard) mapping:

    score = BASE - FACTOR * ln(PD / (1 - PD))

which is strictly *monotonic decreasing* in PD, then clamp to the 300-850 range.
``FACTOR`` is set from a "points to double the odds" (PDO) of 50
(``FACTOR = PDO / ln 2 ≈ 72.13``); ``BASE`` anchors the score at PD = 0.5. With
these constants a base-rate borrower (PD ≈ 0.15) scores ~620, a strong borrower
(PD ≈ 0.03) ~760, and a high-risk borrower (PD ≈ 0.5) ~495 — a realistic spread.

**Risk tiers.** Documented PD cutoffs (calibrated to the ~15% base rate):

    A  PD < 0.05      excellent
    B  0.05 <= PD < 0.10
    C  0.10 <= PD < 0.20
    D  0.20 <= PD < 0.35
    E  PD ≥ 0.35      high risk
"""

from __future__ import annotations

import math

from app.domain.enums import RiskTier

SCORE_MIN = 300
SCORE_MAX = 850
PDO = 50.0
FACTOR = PDO / math.log(2)  # ≈ 72.13
BASE = 495.0  # score at PD = 0.5 (ln-odds = 0)

# Lower bound (exclusive upper) of each tier, ordered best → worst.
TIER_CUTOFFS: tuple[tuple[RiskTier, float], ...] = (
    (RiskTier.A, 0.05),
    (RiskTier.B, 0.10),
    (RiskTier.C, 0.20),
    (RiskTier.D, 0.35),
    (RiskTier.E, 1.01),
)

_EPS = 1e-6


def pd_to_score(pd: float) -> int:
    """Energy Credit Score (300-850) for a default probability."""
    p = min(max(pd, _EPS), 1.0 - _EPS)
    raw = BASE - FACTOR * math.log(p / (1.0 - p))
    return int(round(min(max(raw, SCORE_MIN), SCORE_MAX)))


def pd_to_tier(pd: float) -> RiskTier:
    """Risk tier for a default probability."""
    for tier, upper in TIER_CUTOFFS:
        if pd < upper:
            return tier
    return RiskTier.E


def is_approved(pd: float, threshold: float) -> bool:
    """A loan is approved when PD is below the decision threshold."""
    return pd < threshold
