# Stage 3 Report — ML Platform: Features, Training, Registry, Explainability

## 1. Stage name & objective
**Stage 3 — ML platform.** Turn the synthetic cooperative data into a *real,
honest* default-risk model with the full production scaffolding: a deterministic
feature-engineering pipeline (shared by training and inference, with solo and
pooled variants), an XGBoost training pipeline with class-imbalance handling and
probability calibration, evaluation reporting ROC-AUC / PR-AUC / Brier /
confusion matrix with an explicit **leakage guard**, **MLflow** experiment
tracking + a versioned model registry, **SHAP** per-prediction explanations, an
auto-generated **model card**, and a **PSI drift monitor**. The headline
acceptance — a realistic AUC with `payg_repayment_rate` and `prior_defaults`
ranked at the top — holds.

## 2. What was built
- **Feature schema** (`app/ml/feature_schema.py`) — the canonical nine features
  (Appendix A) with human labels, direction, strength, and bounds; one source of
  truth for ordering used everywhere downstream.
- **Feature engineering** (`app/ml/features.py`) — `FeatureExtractor` turning
  raw events + enrichment signals into the feature vector, for **SOLO** (home
  operator only) and **POOLED** (full cooperative) views. Enrichment signals are
  customer-level and shared, so the network effect comes specifically from
  pooling repayment history. The same code path serves training and inference
  (no train/serve skew). `app/ml/dataset.py` adapts a generated population to a
  training matrix through this extractor.
- **Model bundle** (`app/ml/model.py`) — `ScoringModel` packaging the calibrated
  classifier, the raw booster (for SHAP), feature order, the training
  distribution (for drift), and metadata; joblib save/load with a feature-order
  integrity check. `CalibratedBoosterClassifier` wraps booster + isotonic.
- **Training pipeline** (`app/ml/training.py`) — stratified split,
  `scale_pos_weight` for imbalance, **out-of-fold isotonic calibration**
  (`cross_val_predict`), evaluation, **leakage guard** (flag AUC > 0.90), MLflow
  logging, and **model registry** registration with a `production` alias.
- **Explainability** (`app/ml/explain.py`) — `ShapExplainer` (TreeExplainer on
  the booster) returning ranked top factors with human labels and direction.
- **Drift monitor** (`app/ml/drift.py`) — PSI per feature vs the training
  distribution, with stable / moderate / significant severity.
- **Model card** (`app/ml/model_card.py`) — generated from the actual run into
  `docs/model_cards/energy-credit-score.md` (cannot drift from what shipped).
- **CLI** (`scripts/train_model.py`) — generate → train → register → save bundle
  → write card, against a local MLflow sqlite registry.

## 3. Key decisions & trade-offs
New ADRs in [`docs/DECISIONS.md`](../DECISIONS.md):
- **ADR-0013** — honest predictive structure (irreducible noise + signal scaling).
- **ADR-0014** — synthetic ground truth in a separate `synthetic_*` table.
- **ADR-0015** — honest model: calibration + explicit leakage guard.
- **ADR-0016** — model packaging: calibrated PD + raw booster for SHAP.
- **ADR-0017** — PSI drift baseline shipped inside the model bundle.
- **ADR-0018** — hand-rolled isotonic calibration (sklearn 1.9 removed
  `cv="prefit"`, and both `FrozenEstimator` and `cv=k` paths misbehave with the
  installed XGBoost — so we calibrate out-of-fold ourselves).
- **ADR-0019** — pin numpy<2 + xgboost<2.1 (SHAP/numba need numpy 1.x; xgboost
  2.0 is CPU-only, avoiding a ~600 MB CUDA dependency).

Honest reporting note: AUC/PR-AUC are computed on **raw** scores (discrimination
is calibration-invariant) and Brier on the **calibrated** probability — so each
metric measures the thing it should.

## 4. File tree delta
```
backend/app/ml/feature_schema.py            (new, Stage 2/3 shared)
backend/app/ml/features.py                  (new)
backend/app/ml/dataset.py                   (new)
backend/app/ml/model.py                     (new)
backend/app/ml/training.py                  (new)
backend/app/ml/explain.py                   (new)
backend/app/ml/drift.py                     (new)
backend/app/ml/model_card.py                (new)
backend/tests/unit/test_features.py         (new)
backend/tests/unit/test_ml.py               (new)
scripts/train_model.py                      (new)
backend/pyproject.toml, backend/uv.lock     (ML deps; numpy<2, xgboost<2.1)
docs/model_cards/energy-credit-score.md     (generated)
docs/DECISIONS.md                           (ADR 0013-0019)
docs/{ARCHITECTURE,README}                  (status)
backend/artifacts/scoring_model.joblib      (gitignored model bundle)
```

## 5. How to run it (from a clean checkout)
```bash
cd backend && uv venv && uv pip install -e ".[dev]"

# Train, register to a local MLflow sqlite registry, save the bundle + card:
uv run python ../scripts/train_model.py --customers 4000 --seed 42
#   -> backend/artifacts/scoring_model.joblib
#   -> docs/model_cards/energy-credit-score.md
#   -> MLflow runs/registry under backend/mlruns/

# Inspect the registry UI (optional):
uv run mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db   # :5000
```

## 6. How to test it (with actual results)
```bash
cd backend
uv run ruff check .     # All checks passed!
uv run black --check .  # 58 files unchanged
uv run mypy             # Success: no issues found in 58 source files
uv run pytest -q        # 46 passed
```
**Result: 46 passed** (unit + integration), ML suite ~63 s, full suite ~2m10s.
Stage 3 tests (`test_features.py`, `test_ml.py`) cover: solo-vs-pooled feature
correctness; the demo customer's solo view being strictly worse; metrics in the
realistic band with `leakage_warning is False`; calibration not worsening Brier;
the **thesis feature ranking** (`payg_repayment_rate` in the top 3); model
registration with a non-empty version; joblib save/load round-trip; SHAP
coherence (excellent repayment *decreases* risk, factors sorted by |contribution|);
and PSI detecting an injected distribution shift.

**End-to-end training (4000 synthetic customers, seed 42), test set n=1001:**

| Metric | Value |
|---|---|
| ROC-AUC | **0.774** (target 0.70–0.82 ✓) |
| PR-AUC | 0.464 |
| Brier (calibrated / uncalibrated) | 0.1044 / 0.1438 |
| Base default rate | 14.8% |
| Leakage warning | False |

Top feature importances: **PAYG on-time repayment rate (0.226)** →
**Prior defaults (0.176)** → Utility payment consistency (0.107) — the product
thesis holds. Calibration improves Brier 0.1438 → 0.1044. Model registered as
version 1 with the `production` alias.

## 7. Screencap / demo notes
- Open `docs/model_cards/energy-credit-score.md` — the generated card with the
  metrics table, the green leakage check, and the feature-importance table led by
  repayment rate + prior defaults.
- `uv run mlflow ui --backend-store-uri sqlite:///backend/mlruns/mlflow.db` shows
  the run, params/metrics, and the registered `gridscore-energy-credit` model.
- The decision-flip *visualisation* and the AUC-vs-operators chart come in
  Stages 7–8; Stage 3 delivers the model and explanations that power them.

## 8. Known issues & gaps
- **Dependency pins for this toolchain:** numpy<2 (SHAP/numba), xgboost<2.1
  (CPU-only). Revisit when SHAP/numba ship numpy-2 wheels (ADR-0019).
- **Calibration is hand-rolled** because `CalibratedClassifierCV` is currently
  incompatible with the installed xgboost/sklearn (ADR-0018); revisit when fixed.
- The bundle (`artifacts/scoring_model.joblib`) is gitignored; it is produced by
  running the CLI (Stage 4's scoring service will load it / fall back to lazy
  training). The `model_version` DB table is populated from MLflow in a later
  stage.
- `mlflow` emits many Pydantic-v2 deprecation warnings (upstream); harmless.

## 9. What Stage 4 will do
**Stage 4 — Scoring service.** Wrap the model in a `ScoringService` that builds
features for a customer from the DB, runs inference, maps PD to a 300–850 Energy
Credit Score with documented risk tiers, attaches SHAP top factors, and — the
differentiator — computes the **cooperative lift** by scoring the same customer
under the solo vs pooled views, persisting a `cooperative_lift` row and proving
the seeded borderline customer flips reject → approve. Consent enforcement and
audit logging wrap every score, with a regression test on the flip.

## 10. Approval gate
**Stage 3 complete — awaiting approval to proceed.**
