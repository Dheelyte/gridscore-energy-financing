"""The empirical network effect: model skill vs. the number of operators pooled.

This is the moat thesis, measured rather than asserted. We grow the cooperative
one operator at a time; at each size *k* only the first *k* operators' repayment
events are visible, so each customer's history is as complete as the cooperative
allows. We **retrain** the model at every size and report the held-out ROC-AUC
(averaged over a few splits to tame split noise) and the average visible history.

Enrichment signals are customer-level (always present), so the AUC gain isolates
the value the *pooled repayment history* adds as more operators join.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedShuffleSplit
from xgboost import XGBClassifier

from app.domain.enums import ScoreView
from app.ml.data_gen.config import GeneratorConfig
from app.ml.data_gen.generator import GeneratedPopulation, SyntheticGenerator
from app.ml.dataset import reference_date_for
from app.ml.feature_schema import FEATURE_NAMES
from app.ml.features import EventRecord, FeatureExtractor, RawCustomerData


@dataclass
class NetworkEffectPoint:
    operators: int
    auc: float
    avg_history_months: float
    customers_covered: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "operators": self.operators,
            "auc": round(self.auc, 4),
            "avg_history_months": round(self.avg_history_months, 2),
            "customers_covered": self.customers_covered,
        }


def _quick_model(scale_pos_weight: float, random_state: int) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=160,
        max_depth=4,
        learning_rate=0.06,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.5,
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=random_state,
        n_jobs=0,
    )


def _features_with_operator_cap(
    population: GeneratedPopulation, k: int, extractor: FeatureExtractor, ref_date: dt.date
) -> tuple[npt.NDArray[np.float64], int]:
    """Pooled features when only the first ``k`` operators are in the cooperative."""
    rows: list[list[float]] = []
    covered = 0
    for c in population.customers:
        events = [
            EventRecord(
                operator_key=str(e.operator_ref),
                due_date=e.due_date,
                paid_date=e.paid_date,
                status=e.status,
                instalment_amount=e.instalment_amount,
            )
            for e in c.events
            if e.operator_ref < k
        ]
        if events:
            covered += 1
        signals = {s.provider_type: dict(s.payload) for s in c.signals}
        raw = RawCustomerData(str(c.home_operator_ref), events, signals)
        feats = extractor.extract(raw, ScoreView.POOLED, reference_date=ref_date)
        rows.append([feats[name] for name in FEATURE_NAMES])
    return np.array(rows, dtype=np.float64), covered


def compute_network_effect(
    config: GeneratorConfig | None = None, *, n_splits: int = 3
) -> list[NetworkEffectPoint]:
    """Retrain on 1..N pooled operators and return the AUC/coverage curve."""
    config = config or GeneratorConfig(n_customers=1500, seed=21)
    population = SyntheticGenerator(config).generate()
    extractor = FeatureExtractor()
    ref_date = reference_date_for(population)
    y = np.array([int(c.default_label) for c in population.customers])

    splitter = StratifiedShuffleSplit(n_splits=n_splits, test_size=0.3, random_state=0)
    folds = list(splitter.split(np.zeros(len(y)), y))

    history_idx = FEATURE_NAMES.index("payg_history_months")
    points: list[NetworkEffectPoint] = []
    for k in range(1, config.n_operators + 1):
        matrix, covered = _features_with_operator_cap(population, k, extractor, ref_date)
        aucs: list[float] = []
        for i, (train_idx, test_idx) in enumerate(folds):
            pos = int(y[train_idx].sum())
            spw = (len(train_idx) - pos) / max(pos, 1)
            model = _quick_model(spw, random_state=i)
            model.fit(matrix[train_idx], y[train_idx])
            aucs.append(
                float(roc_auc_score(y[test_idx], model.predict_proba(matrix[test_idx])[:, 1]))
            )
        points.append(
            NetworkEffectPoint(
                operators=k,
                auc=float(np.mean(aucs)),
                avg_history_months=float(matrix[:, history_idx].mean()),
                customers_covered=covered,
            )
        )
    return points
