"""Provider adapter contract tests (mock implementations)."""

from __future__ import annotations

import pytest

from app.domain.enums import ProviderType
from app.providers.registry import default_providers

pytestmark = pytest.mark.unit

_EXPECTED_KEYS = {
    ProviderType.MOBILE_MONEY: {"avg_monthly_inflow_usd", "inflow_stability"},
    ProviderType.AIRTIME: {"topup_regularity"},
    ProviderType.UTILITY: {"payment_score"},
}

_HASH_A = "a" * 64
_HASH_B = "b3c1" + "0" * 60


async def test_providers_return_expected_contract() -> None:
    for provider in default_providers():
        payload = await provider.fetch_signal(_HASH_A)
        assert set(payload) == _EXPECTED_KEYS[provider.provider_type]
        for value in payload.values():
            assert isinstance(value, float)
        # bounded [0,1] scores; inflow is a positive USD amount
        for key, value in payload.items():
            if key == "avg_monthly_inflow_usd":
                assert 0 < value <= 5000
            else:
                assert 0.0 <= value <= 1.0


async def test_signals_are_deterministic_per_identity() -> None:
    for provider in default_providers():
        assert await provider.fetch_signal(_HASH_A) == await provider.fetch_signal(_HASH_A)


async def test_signals_vary_across_customers() -> None:
    mm = default_providers()[0]
    assert await mm.fetch_signal(_HASH_A) != await mm.fetch_signal(_HASH_B)
