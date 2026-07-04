"""Enrichment provider **ports** (hexagonal architecture).

Each provider returns one customer-level signal payload. Real integrations
(MTN MoMo, Open Banking, a telco airtime API) implement these interfaces later;
Stage 6 ships deterministic mocks. Services depend only on the abstract port, so
swapping in a real adapter requires no change to the ingestion/enrichment code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.enums import ProviderType


class EnrichmentProvider(ABC):
    """Fetches one provider's signal payload for an (already anonymised) customer."""

    provider_type: ProviderType

    @abstractmethod
    async def fetch_signal(self, identity_hash: str) -> dict[str, float]:
        """Return the signal payload for ``identity_hash`` (a salted hash, not PII)."""


class MobileMoneyProvider(EnrichmentProvider):
    """Mobile-money inflows: ``avg_monthly_inflow_usd`` and ``inflow_stability``."""

    provider_type = ProviderType.MOBILE_MONEY


class AirtimeProvider(EnrichmentProvider):
    """Airtime top-ups: ``topup_regularity``."""

    provider_type = ProviderType.AIRTIME


class UtilityProvider(EnrichmentProvider):
    """Other bill payments: ``payment_score``."""

    provider_type = ProviderType.UTILITY
