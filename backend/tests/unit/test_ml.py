"""Training, calibration, SHAP explanations, drift, and model persistence.

These exercise the real XGBoost + MLflow + SHAP stack on a small synthetic
population. MLflow uses a throwaway sqlite registry in a temp directory.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.domain.enums import ScoreView
from app.ml.data_gen import GeneratorConfig, SyntheticGenerator
from app.ml.data_gen.generator import GeneratedPopulation
from app.ml.dataset import build_dataset, raw_from_generated, reference_date_for
from app.ml.drift import DriftSeverity, compute_drift
from app.ml.explain import ShapExplainer
from app.ml.features import FeatureExtractor
from app.ml.model import ScoringModel
from app.ml.training import TrainingResult, train

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def population() -> GeneratedPopulation:
    return SyntheticGenerator(GeneratorConfig(n_customers=2500, seed=2025)).generate()


@pytest.fixture(scope="module")
def trained(
    population: GeneratedPopulation, tmp_path_factory: pytest.TempPathFactory
) -> TrainingResult:
    tracking = tmp_path_factory.mktemp("mlruns")
    uri = f"sqlite:///{tracking / 'mlflow.db'}"
    return train(population, tracking_uri=uri)


def test_metrics_are_realistic_and_not_leaking(trained: TrainingResult) -> None:
    auc = trained.metrics["roc_auc"]
    assert 0.70 <= auc <= 0.86  # realistic band (Appendix A target ~0.70-0.82)
    assert trained.leakage_warning is False
    assert 0.0 < trained.metrics["pr_auc"] < 1.0


def test_calibration_does_not_worsen_brier(trained: TrainingResult) -> None:
    # Calibration should keep the Brier score competitive with the raw model.
    assert trained.metrics["brier"] <= trained.metrics["brier_uncalibrated"] + 0.01


def test_thesis_feature_ranks_at_top(trained: TrainingResult) -> None:
    top3 = list(trained.feature_importances)[:3]
    # The product thesis: PAYG repayment rate is at or near the top.
    assert "payg_repayment_rate" in top3


def test_model_registered_with_version(trained: TrainingResult) -> None:
    assert trained.run_id
    assert trained.model_version not in ("", "0")


def test_model_save_load_roundtrip(trained: TrainingResult, tmp_path: Path) -> None:
    feats = {n: 0.5 for n in trained.model.feature_names}
    path = trained.model.save(tmp_path / "m.joblib")
    reloaded = ScoringModel.load(path)
    assert reloaded.predict_pd(feats) == pytest.approx(trained.model.predict_pd(feats))


def test_shap_explanation_is_coherent(
    population: GeneratedPopulation, trained: TrainingResult
) -> None:
    explainer = ShapExplainer(trained.model)
    # A clearly strong customer: high repayment rate, no prior defaults.
    feats = {n: 0.5 for n in trained.model.feature_names}
    feats["payg_repayment_rate"] = 0.99
    feats["prior_defaults"] = 0.0
    factors = explainer.explain(feats, top_k=5)

    assert len(factors) == 5
    mags = [abs(f.contribution) for f in factors]
    assert mags == sorted(mags, reverse=True)  # sorted by importance
    # Excellent repayment should reduce default risk where it appears.
    rate_factor = next((f for f in factors if f.feature == "payg_repayment_rate"), None)
    if rate_factor is not None:
        assert rate_factor.direction == "decreases"


def test_drift_detects_distribution_shift(
    population: GeneratedPopulation, trained: TrainingResult
) -> None:
    dataset = build_dataset(population)
    dist = trained.model.training_distribution

    # Same distribution -> stable.
    stable = compute_drift(dist, dataset.X)
    assert stable.overall is DriftSeverity.STABLE

    # Shift repayment rate sharply downward -> significant drift.
    shifted = dataset.X.copy()
    rate_idx = dataset.feature_names.index("payg_repayment_rate")
    shifted[:, rate_idx] = np.clip(shifted[:, rate_idx] - 0.4, 0, 1)
    report = compute_drift(dist, shifted)
    assert report.max_psi > stable.max_psi
    assert report.overall in (DriftSeverity.MODERATE, DriftSeverity.SIGNIFICANT)


def test_solo_view_degrades_demo_customer(population: GeneratedPopulation) -> None:
    """End-to-end feature check: the demo customer's solo view is worse."""
    demo = next(c for c in population.customers if c.is_demo)
    ex = FeatureExtractor()
    ref = reference_date_for(population)
    raw = raw_from_generated(demo)
    solo = ex.extract(raw, ScoreView.SOLO, reference_date=ref)
    pooled = ex.extract(raw, ScoreView.POOLED, reference_date=ref)
    assert solo["payg_repayment_rate"] < pooled["payg_repayment_rate"]
    assert solo["payg_history_months"] < pooled["payg_history_months"]
