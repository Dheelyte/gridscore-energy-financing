"""Training pipeline: fit, calibrate, evaluate, and register an honest model.

Pipeline:
1. Build features from the generated population (pooled view) via the shared
   extractor — no train/serve skew.
2. Stratified train/test split; a further fit/calibration split.
3. Fit an XGBoost classifier with ``scale_pos_weight`` for class imbalance.
4. Calibrate probabilities (Platt/isotonic) on the held-out calibration set.
5. Evaluate on the untouched test set: ROC-AUC, PR-AUC, Brier (before & after
   calibration), and a confusion matrix at the decision threshold.
6. **Leakage guard**: flag a suspiciously high ROC-AUC (> 0.90).
7. Log params/metrics/model to MLflow and register a versioned model.
8. Package a :class:`ScoringModel` bundle (calibrated model + booster + training
   distribution) for the scoring service.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field

import mlflow
import mlflow.sklearn
import numpy as np
import numpy.typing as npt
from mlflow.tracking import MlflowClient
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    roc_auc_score,
)
from sklearn.model_selection import cross_val_predict, train_test_split
from xgboost import XGBClassifier

from app.ml.data_gen.generator import GeneratedPopulation
from app.ml.dataset import build_dataset
from app.ml.drift import build_feature_distribution
from app.ml.model import CalibratedBoosterClassifier, ScoringModel

# Above this ROC-AUC we treat the result as a likely-leakage smell to investigate
# rather than a win (Appendix A / honesty posture).
LEAKAGE_AUC_THRESHOLD = 0.90


@dataclass
class TrainingConfig:
    test_size: float = 0.25
    calibration_folds: int = 5  # out-of-fold folds for isotonic calibration
    random_state: int = 42
    # Approve/reject PD boundary (business choice): set near the base default rate
    # so only below-average-risk borrowers are approved. Must match the runtime
    # default in app.core.config so the model card's confusion matrix reflects the
    # operating point the API actually uses.
    decision_threshold: float = 0.12

    # XGBoost — deliberately shallow/regularised so it recovers the signal without
    # overfitting toward the Bayes ceiling.
    n_estimators: int = 300
    max_depth: int = 4
    learning_rate: float = 0.05
    subsample: float = 0.9
    colsample_bytree: float = 0.9
    reg_lambda: float = 1.5

    experiment_name: str = "gridscore-default-risk"
    registered_model_name: str = "gridscore-energy-credit"


@dataclass
class TrainingResult:
    model: ScoringModel
    metrics: dict[str, float]
    feature_importances: dict[str, float]
    confusion: dict[str, int]
    run_id: str
    model_version: str
    leakage_warning: bool
    extras: dict[str, object] = field(default_factory=dict)


def _xgb(config: TrainingConfig, scale_pos_weight: float) -> XGBClassifier:
    return XGBClassifier(
        n_estimators=config.n_estimators,
        max_depth=config.max_depth,
        learning_rate=config.learning_rate,
        subsample=config.subsample,
        colsample_bytree=config.colsample_bytree,
        reg_lambda=config.reg_lambda,
        scale_pos_weight=scale_pos_weight,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=config.random_state,
        n_jobs=0,
    )


def train(
    population: GeneratedPopulation,
    *,
    tracking_uri: str,
    config: TrainingConfig | None = None,
) -> TrainingResult:
    config = config or TrainingConfig()
    dataset = build_dataset(population)
    X, y, names = dataset.X, dataset.y, dataset.feature_names

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.test_size, stratify=y, random_state=config.random_state
    )

    pos = int(y_train.sum())
    neg = int(len(y_train) - pos)
    scale_pos_weight = neg / max(pos, 1)

    # Out-of-fold raw probabilities give an unbiased basis for calibration while
    # letting the final booster train on the entire training split.
    oof = cross_val_predict(
        _xgb(config, scale_pos_weight),
        X_train,
        y_train,
        cv=config.calibration_folds,
        method="predict_proba",
    )[:, 1]
    isotonic = IsotonicRegression(out_of_bounds="clip")
    isotonic.fit(oof, y_train)

    booster = _xgb(config, scale_pos_weight)
    booster.fit(X_train, y_train)
    calibrated = CalibratedBoosterClassifier(booster, isotonic)

    # -- evaluation on the untouched test set -- #
    # AUC/PR-AUC measure discrimination (ranking), reported on the raw model;
    # isotonic calibration is monotonic so it does not change discrimination.
    # Brier measures calibration, reported on the served (calibrated) probability.
    pd_test = calibrated.predict_proba(X_test)[:, 1]
    raw_test = booster.predict_proba(X_test)[:, 1]
    roc_auc = float(roc_auc_score(y_test, raw_test))
    pr_auc = float(average_precision_score(y_test, raw_test))
    brier = float(brier_score_loss(y_test, pd_test))
    brier_uncalibrated = float(brier_score_loss(y_test, raw_test))

    preds = (pd_test >= config.decision_threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_test, preds).ravel()
    confusion = {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}

    importances = _feature_importances(booster, names)
    leakage_warning = roc_auc > LEAKAGE_AUC_THRESHOLD

    metrics = {
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "brier": brier,
        "brier_uncalibrated": brier_uncalibrated,
        "base_rate": float(y.mean()),
        "n_train": float(len(y_train)),
        "n_test": float(len(y_test)),
    }

    run_id, version = _log_to_mlflow(
        tracking_uri=tracking_uri,
        config=config,
        model=calibrated,
        metrics=metrics,
        importances=importances,
        confusion=confusion,
        leakage_warning=leakage_warning,
        sample=X_test[:5],
    )

    model = ScoringModel(
        version=version,
        calibrated_model=calibrated,
        booster=booster,
        feature_names=names,
        threshold=config.decision_threshold,
        metrics=metrics,
        training_distribution=build_feature_distribution(X_train, names),
        mlflow_run_id=run_id,
    )

    return TrainingResult(
        model=model,
        metrics=metrics,
        feature_importances=importances,
        confusion=confusion,
        run_id=run_id,
        model_version=version,
        leakage_warning=leakage_warning,
    )


def _feature_importances(booster: XGBClassifier, names: tuple[str, ...]) -> dict[str, float]:
    raw = booster.feature_importances_
    pairs = sorted(zip(names, raw, strict=True), key=lambda p: p[1], reverse=True)
    return {name: float(value) for name, value in pairs}


def _log_to_mlflow(
    *,
    tracking_uri: str,
    config: TrainingConfig,
    model: CalibratedBoosterClassifier,
    metrics: dict[str, float],
    importances: dict[str, float],
    confusion: dict[str, int],
    leakage_warning: bool,
    sample: npt.NDArray[np.float64],
) -> tuple[str, str]:
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(config.experiment_name)

    with mlflow.start_run() as run:
        mlflow.log_params(
            {
                "model": "xgboost+isotonic",
                "n_estimators": config.n_estimators,
                "max_depth": config.max_depth,
                "learning_rate": config.learning_rate,
                "decision_threshold": config.decision_threshold,
            }
        )
        mlflow.log_metrics(metrics)
        mlflow.log_metrics({f"importance.{k}": v for k, v in importances.items()})
        mlflow.log_metrics({f"confusion.{k}": v for k, v in confusion.items()})
        mlflow.set_tag("leakage_warning", str(leakage_warning))
        mlflow.set_tag("data", "synthetic")

        # Log the full calibrated estimator (what we actually serve) via the
        # sklearn flavor — robust across the installed xgboost/sklearn versions.
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            input_example=sample,
            registered_model_name=config.registered_model_name,
        )
        run_id = run.info.run_id

    version = _latest_version(tracking_uri, config.registered_model_name, run_id)
    return run_id, version


def _latest_version(tracking_uri: str, name: str, run_id: str) -> str:
    """Resolve the registered version for this run and mark it production."""
    client = MlflowClient(tracking_uri=tracking_uri)
    versions = client.search_model_versions(f"run_id='{run_id}'")
    if not versions:
        return "0"
    version = max(versions, key=lambda v: int(v.version)).version
    with contextlib.suppress(Exception):  # alias support varies by backend
        client.set_registered_model_alias(name, "production", version)
    return str(version)
