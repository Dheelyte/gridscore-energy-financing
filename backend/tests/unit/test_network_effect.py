"""The empirical network effect: model skill grows as operators pool their data."""

from __future__ import annotations

import pytest

from app.ml.data_gen.config import GeneratorConfig
from app.services.analytics.network_effect import compute_network_effect

pytestmark = pytest.mark.unit


def test_auc_and_coverage_increase_with_operators() -> None:
    # Uses the endpoint's own config so the test exercises what ships.
    points = compute_network_effect(GeneratorConfig(n_customers=1200, seed=21), n_splits=3)
    assert len(points) == GeneratorConfig().n_operators
    assert [p.operators for p in points] == [1, 2, 3, 4, 5]

    # Coverage (visible history) grows monotonically as operators join — the
    # structural heart of the network effect: a customer is only as visible as
    # the cooperative is large.
    history = [p.avg_history_months for p in points]
    assert history == sorted(history)
    assert history[-1] > history[0]
    assert [p.customers_covered for p in points] == sorted(p.customers_covered for p in points)

    # And the model is genuinely sharper with the full cooperative than with one
    # operator (empirical, from retraining).
    assert points[-1].auc > points[0].auc
    assert all(0.6 <= p.auc <= 0.86 for p in points)  # realistic band, no leakage
