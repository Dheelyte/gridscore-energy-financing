"""Population Stability Index (PSI) drift monitoring.

PSI compares the distribution of each feature in a candidate batch against the
training distribution. Convention:

* PSI < 0.10  — stable
* 0.10-0.25   — moderate shift (watch)
* > 0.25      — significant shift (investigate / consider retraining)

The training distribution is captured at fit time (quantile bins) and shipped
inside the :class:`ScoringModel`, so drift can be checked online without the
training data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from app.ml.model import FeatureDistribution

_EPS = 1e-6


class DriftSeverity(StrEnum):
    STABLE = "stable"
    MODERATE = "moderate"
    SIGNIFICANT = "significant"


def _severity(psi: float) -> DriftSeverity:
    if psi < 0.10:
        return DriftSeverity.STABLE
    if psi < 0.25:
        return DriftSeverity.MODERATE
    return DriftSeverity.SIGNIFICANT


def build_feature_distribution(
    matrix: npt.NDArray[np.float64],
    feature_names: tuple[str, ...],
    *,
    n_bins: int = 10,
) -> FeatureDistribution:
    """Capture per-feature quantile bin edges and densities from training data."""
    bin_edges: dict[str, list[float]] = {}
    bin_density: dict[str, list[float]] = {}
    quantiles = np.linspace(0, 1, n_bins + 1)
    for i, name in enumerate(feature_names):
        col = matrix[:, i]
        edges = np.unique(np.quantile(col, quantiles))
        if edges.size < 2:  # constant feature
            edges = np.array([col.min() - 0.5, col.max() + 0.5])
        edges[0], edges[-1] = -np.inf, np.inf
        counts, _ = np.histogram(col, bins=edges)
        density = counts / max(counts.sum(), 1)
        bin_edges[name] = edges.tolist()
        bin_density[name] = density.tolist()
    return FeatureDistribution(
        feature_names=feature_names, bin_edges=bin_edges, bin_density=bin_density
    )


def _psi(train_density: npt.NDArray[np.float64], cand_density: npt.NDArray[np.float64]) -> float:
    train = np.clip(train_density, _EPS, None)
    cand = np.clip(cand_density, _EPS, None)
    return float(np.sum((cand - train) * np.log(cand / train)))


@dataclass
class FeatureDrift:
    feature: str
    psi: float
    severity: DriftSeverity


@dataclass
class DriftReport:
    features: list[FeatureDrift]
    max_psi: float
    overall: DriftSeverity

    def as_dict(self) -> dict[str, object]:
        return {
            "overall": str(self.overall),
            "max_psi": round(self.max_psi, 4),
            "features": {f.feature: round(f.psi, 4) for f in self.features},
        }


def compute_drift(
    distribution: FeatureDistribution,
    candidate: npt.NDArray[np.float64],
) -> DriftReport:
    """PSI per feature for a candidate batch vs the training distribution."""
    drifts: list[FeatureDrift] = []
    for i, name in enumerate(distribution.feature_names):
        edges = np.array(distribution.bin_edges[name])
        train_density = np.array(distribution.bin_density[name])
        counts, _ = np.histogram(candidate[:, i], bins=edges)
        cand_density = counts / max(counts.sum(), 1)
        psi = _psi(train_density, cand_density)
        drifts.append(FeatureDrift(feature=name, psi=psi, severity=_severity(psi)))

    max_psi = max((d.psi for d in drifts), default=0.0)
    return DriftReport(features=drifts, max_psi=max_psi, overall=_severity(max_psi))
