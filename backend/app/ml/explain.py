"""Per-prediction explanations via SHAP.

Powers the "top factors" UI: for a single customer, which features pushed the
default probability up or down, and by how much. We use ``TreeExplainer`` on the
raw XGBoost booster (the calibration wrapper is not a tree model), which gives
exact, additive SHAP values in log-odds space.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import shap

from app.ml.feature_schema import FEATURE_BY_NAME
from app.ml.model import ScoringModel


@dataclass
class TopFactor:
    feature: str
    label: str
    value: float
    contribution: float  # SHAP value (log-odds); >0 increases default risk
    direction: str  # "increases" | "decreases" risk for this customer

    def as_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "label": self.label,
            "value": round(self.value, 4),
            "contribution": round(self.contribution, 4),
            "direction": self.direction,
        }


class ShapExplainer:
    """Wraps a SHAP TreeExplainer bound to a model's booster."""

    def __init__(self, model: ScoringModel) -> None:
        self._model = model
        self._explainer = shap.TreeExplainer(model.booster)

    def explain(self, features: dict[str, float], *, top_k: int = 5) -> list[TopFactor]:
        matrix = self._model.vectorise(features)
        shap_values = self._explainer.shap_values(matrix)
        values = np.asarray(shap_values)
        # Binary classifiers may return (n, f) or a list/3-D array; normalise to
        # the contributions toward the positive (default) class.
        if values.ndim == 3:
            values = values[..., -1]
        row = values[0]

        factors = [
            TopFactor(
                feature=name,
                label=FEATURE_BY_NAME[name].label,
                value=features[name],
                contribution=float(row[i]),
                direction="increases" if row[i] > 0 else "decreases",
            )
            for i, name in enumerate(self._model.feature_names)
        ]
        factors.sort(key=lambda f: abs(f.contribution), reverse=True)
        return factors[:top_k]
