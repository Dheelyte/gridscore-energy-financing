"""The serialised scoring model bundle.

A :class:`ScoringModel` packages everything the scoring service needs at
inference time:

* the **calibrated** classifier (well-behaved probabilities), used for the PD;
* the raw XGBoost **booster**, used by the SHAP explainer (TreeExplainer needs
  the tree model, not the calibration wrapper);
* the canonical feature order;
* the **training feature distribution** (for PSI drift monitoring);
* metadata (version, metrics, training timestamp).

The bundle is persisted with joblib and is the single artifact Stage 4 loads.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import numpy.typing as npt

from app.ml.feature_schema import FEATURE_NAMES


@dataclass
class FeatureDistribution:
    """Per-feature training quantile bin edges + densities, for PSI drift."""

    feature_names: tuple[str, ...]
    bin_edges: dict[str, list[float]]
    bin_density: dict[str, list[float]]


class CalibratedBoosterClassifier:
    """A booster + isotonic calibrator with a scikit-learn-style ``predict_proba``.

    We calibrate by hand rather than via ``CalibratedClassifierCV`` because that
    estimator's prefit/cv paths are currently incompatible with the installed
    xgboost + scikit-learn versions. Isotonic regression is monotonic, so it
    sharpens probabilities (Brier) without changing the model's ranking (AUC).
    Defined at module scope so it pickles cleanly into the bundle and MLflow.
    """

    def __init__(self, booster: Any, isotonic: Any) -> None:
        self.booster = booster
        self.isotonic = isotonic
        self.classes_ = np.array([0, 1])

    def predict_proba(self, X: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        raw = self.booster.predict_proba(X)[:, 1]
        calibrated = np.clip(self.isotonic.predict(raw), 0.0, 1.0)
        return np.column_stack([1.0 - calibrated, calibrated])

    def predict(self, X: npt.NDArray[np.float64]) -> npt.NDArray[np.int64]:
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(np.int64)


@dataclass
class ScoringModel:
    version: str
    calibrated_model: Any  # sklearn CalibratedClassifierCV
    booster: Any  # xgboost.XGBClassifier (for SHAP)
    feature_names: tuple[str, ...]
    threshold: float  # default approve/reject decision boundary on PD
    metrics: dict[str, float]
    training_distribution: FeatureDistribution
    mlflow_run_id: str | None = None
    created_at: dt.datetime = field(default_factory=lambda: dt.datetime.now(dt.UTC))

    def vectorise(self, features: dict[str, float]) -> npt.NDArray[np.float64]:
        """Order a feature dict into the model's expected 1xN matrix."""
        return np.array([[features[name] for name in self.feature_names]], dtype=np.float64)

    def predict_pd(self, features: dict[str, float]) -> float:
        """Calibrated probability of default for one customer."""
        proba = self.calibrated_model.predict_proba(self.vectorise(features))[0, 1]
        return float(proba)

    def predict_pd_batch(self, matrix: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        proba: npt.NDArray[np.float64] = self.calibrated_model.predict_proba(matrix)[:, 1]
        return proba

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        return path

    @staticmethod
    def load(path: str | Path) -> ScoringModel:
        model: ScoringModel = joblib.load(path)
        if tuple(model.feature_names) != FEATURE_NAMES:
            raise ValueError("Loaded model feature order does not match the schema")
        return model
