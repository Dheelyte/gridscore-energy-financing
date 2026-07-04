"""Mock provider adapters — deterministic, realistic signals for demos & tests.

Signals are seeded from the customer's identity hash, so the same customer always
yields the same payload (idempotent enrichment) while different customers vary.
A single per-customer latent "quality" makes the three signals plausibly
correlated, like a real person's financial footprint.
"""

from __future__ import annotations

import numpy as np

from app.providers.base import AirtimeProvider, MobileMoneyProvider, UtilityProvider


def _rng(identity_hash: str) -> np.random.Generator:
    seed = int(identity_hash[:16], 16) % (2**32)
    return np.random.default_rng(seed)


def _quality(identity_hash: str) -> float:
    """A stable per-customer latent quality in [0, 1]."""
    return float(int(identity_hash[16:24] or "0", 16) % 1000) / 1000.0


class MockMobileMoneyProvider(MobileMoneyProvider):
    async def fetch_signal(self, identity_hash: str) -> dict[str, float]:
        rng = _rng(identity_hash)
        q = _quality(identity_hash)
        inflow = float(np.clip(np.exp(rng.normal(np.log(140) + 0.5 * q, 0.4)), 20, 5000))
        stability = float(np.clip(0.45 + 0.4 * q + rng.normal(0, 0.08), 0.02, 0.99))
        return {
            "avg_monthly_inflow_usd": round(inflow, 2),
            "inflow_stability": round(stability, 4),
        }


class MockAirtimeProvider(AirtimeProvider):
    async def fetch_signal(self, identity_hash: str) -> dict[str, float]:
        rng = _rng(identity_hash)
        q = _quality(identity_hash)
        regularity = float(np.clip(0.4 + 0.45 * q + rng.normal(0, 0.1), 0.02, 0.99))
        return {"topup_regularity": round(regularity, 4)}


class MockUtilityProvider(UtilityProvider):
    async def fetch_signal(self, identity_hash: str) -> dict[str, float]:
        rng = _rng(identity_hash)
        q = _quality(identity_hash)
        score = float(np.clip(0.4 + 0.45 * q + rng.normal(0, 0.1), 0.02, 0.99))
        return {"payment_score": round(score, 4)}
