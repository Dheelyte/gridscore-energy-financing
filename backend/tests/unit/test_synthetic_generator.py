"""Tests for the synthetic data engine (no database).

These assert the *statistical* properties that make the data credible: a
realistic base default rate, an honest (not perfect) achievable AUC, and the
product-thesis feature ranking. They also pin the cooperative split and the
borderline demo customer.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pytest

from app.domain.enums import ConsentScope, RepaymentStatus
from app.ml.data_gen import (
    GeneratedCustomer,
    GeneratedPopulation,
    GeneratorConfig,
    SyntheticGenerator,
)
from app.ml.feature_schema import FEATURE_NAMES

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def population() -> GeneratedPopulation:
    return SyntheticGenerator(GeneratorConfig(n_customers=3000, seed=2024)).generate()


def _labels(pop: GeneratedPopulation) -> npt.NDArray[np.float64]:
    return np.array([c.default_label for c in pop.customers], dtype=float)


def test_base_default_rate_in_realistic_range(population: GeneratedPopulation) -> None:
    assert 0.10 <= population.default_rate <= 0.20


def test_achievable_auc_is_realistic_not_perfect(population: GeneratedPopulation) -> None:
    # The feature-signal ceiling should be credible (~0.75-0.82), so the Stage 3
    # model lands in range rather than suspiciously high.
    assert 0.72 <= population.bayes_auc() <= 0.86


def test_feature_values_are_in_schema_ranges(population: GeneratedPopulation) -> None:
    for c in population.customers:
        f = c.latent_features
        assert set(f) == set(FEATURE_NAMES)
        assert 0.0 <= f["payg_repayment_rate"] <= 1.0
        assert 0.0 <= f["mm_inflow_stability"] <= 1.0
        assert f["prior_defaults"] >= 0
        assert f["loan_to_income"] > 0
        assert f["payg_history_months"] >= 3


def test_repayment_rate_and_prior_defaults_are_the_strongest_signals(
    population: GeneratedPopulation,
) -> None:
    """The product thesis: PAYG repayment rate and prior defaults dominate."""
    y = _labels(population)
    corr = {
        name: abs(np.corrcoef([c.latent_features[name] for c in population.customers], y)[0, 1])
        for name in FEATURE_NAMES
    }
    ranked = sorted(corr, key=lambda k: corr[k], reverse=True)
    assert set(ranked[:2]) == {"payg_repayment_rate", "prior_defaults"}

    # Directions match Appendix A.
    rate = np.array([c.latent_features["payg_repayment_rate"] for c in population.customers])
    pri = np.array([c.latent_features["prior_defaults"] for c in population.customers])
    assert np.corrcoef(rate, y)[0, 1] < 0  # protective
    assert np.corrcoef(pri, y)[0, 1] > 0  # risk


def test_label_is_not_trivially_recoverable_from_repayment_history(
    population: GeneratedPopulation,
) -> None:
    """No leakage: defaulters are not simply 'everyone with a low on-time rate'."""
    defaulter_rates = [c.pooled_on_time_rate() for c in population.customers if c.default_label]
    # Plenty of customers who default still have strong observed repayment — the
    # outcome carries irreducible noise beyond the visible history.
    assert max(defaulter_rates) > 0.8


def test_determinism(population: GeneratedPopulation) -> None:
    again = SyntheticGenerator(GeneratorConfig(n_customers=3000, seed=2024)).generate()
    assert again.default_rate == population.default_rate
    assert again.customers[0].identity_hash == population.customers[0].identity_hash
    assert again.customers[10].latent_features == population.customers[10].latent_features


def test_some_customers_lack_scoring_consent(population: GeneratedPopulation) -> None:
    def has_scoring_consent(c: GeneratedCustomer) -> bool:
        return any(k.scope is ConsentScope.SCORING and k.granted for k in c.consents)

    non_demo = [c for c in population.customers if not c.is_demo]
    without = [c for c in non_demo if not has_scoring_consent(c)]
    assert 0 < len(without) < len(non_demo)  # gating will matter, but not for everyone


def test_borderline_demo_customer_setup(population: GeneratedPopulation) -> None:
    demo = next(c for c in population.customers if c.is_demo)
    assert demo.scenario == "borderline_flip"
    assert demo.default_label is False  # genuinely reliable
    assert demo.identity_hash == SyntheticGenerator.demo_identity_hash()

    # The cooperative structural setup: the home (solo) slice looks far worse
    # than the full pooled history.
    home_events = [e for e in demo.events if e.operator_ref == demo.home_operator_ref]
    assert len(home_events) < len(demo.events)
    assert demo.solo_on_time_rate() < 0.5
    assert demo.pooled_on_time_rate() > 0.85

    # No defaults in the demo customer's history (prior_defaults == 0).
    assert all(e.status is not RepaymentStatus.DEFAULTED for e in demo.events)
