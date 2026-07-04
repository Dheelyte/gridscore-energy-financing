"""Provider registry — the swap point between mock and real adapters."""

from __future__ import annotations

from app.providers.base import EnrichmentProvider
from app.providers.mock import (
    MockAirtimeProvider,
    MockMobileMoneyProvider,
    MockUtilityProvider,
)


def default_providers() -> list[EnrichmentProvider]:
    """The provider set used for enrichment. Mocks today; real adapters drop in
    here later without touching the enrichment service."""
    return [
        MockMobileMoneyProvider(),
        MockAirtimeProvider(),
        MockUtilityProvider(),
    ]
