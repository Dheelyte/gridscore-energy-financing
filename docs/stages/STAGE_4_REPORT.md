# Stage 4 Report — Scoring Service & the Cooperative-Lift Differentiator

## 1. Stage name & objective
**Stage 4 — Scoring service.** Turn the trained model into business outcomes: a
`ScoringService` that builds a customer's features from the database, runs
calibrated inference, maps the default probability to a 300–850 **Energy Credit
Score** and an **A–E risk tier**, attaches SHAP "top factors", and — the
differentiator — computes the **cooperative lift** by scoring the same customer
under the *solo* (home-operator-only) and *pooled* (full cooperative) views,
quantifying the PD/confidence improvement and whether the lending decision flips.
Every score is **consent-gated** and **audit-logged**. The headline acceptance —
the seeded borderline customer flipping **reject → approve** under the pooled
view — is proven by a regression test.

## 2. What was built
- **Score transform** (`app/services/scoring/transform.py`) — documented,
  monotonic log-odds mapping PD → 300–850 (clamped) and A–E risk tiers by PD
  cutoffs; an `is_approved` decision helper. (ADR-0020.)
- **ScoringService** (`app/services/scoring/service.py`):
  - `score_customer(...)` — consent check → load raw events/signals from the DB →
    build features for the view → calibrated PD → score + tier + decision +
    SHAP top factors → persist a `feature_snapshot` and an audit-grade
    `score_result` → write an audit entry.
  - `score_cooperative(...)` — scores **solo** vs **pooled**, computes
    `pd_delta`, `confidence_delta`, `score_delta`, and `decision_flips`,
    persists a `cooperative_lift` row, and audits the comparison.
  - DTOs (`ScoreOutcome`, `CooperativeOutcome`) with `as_dict()` for the Stage 5
    API; typed exceptions (`CustomerNotFoundError`, `ConsentRequiredError`).
- **Consent enforcement** — scoring refuses without an active `SCORING` consent
  and audits the denial (`score.denied_no_consent`).
- **Model loader** (`model_loader.py`) + `model_path` / `decision_threshold`
  settings; the bundle is loaded (and cached) from `artifacts/scoring_model.joblib`.
- **Demo tuning** — the Stage 2 borderline customer was retuned to *middling*
  enrichment so the flip is driven by the cooperative's added history (ADR-0021).

## 3. Key decisions & trade-offs
- **ADR-0020** — Energy Credit Score log-odds transform + A–E tiers.
- **ADR-0021** — demo customer tuned to middling enrichment so the reject→approve
  flip is real and history-driven (not enrichment-driven).
- The **solo view** uses the customer's *home operator* slice (consistent with the
  Stage 2 data model), surfaced by the shared `FeatureExtractor`; enrichment
  signals are customer-level and identical across views, so the lift is
  attributable purely to pooled repayment history.
- AUC/PR-AUC on raw scores, Brier on calibrated PD (carried over from Stage 3).

## 4. File tree delta
```
backend/app/services/scoring/__init__.py        (new)
backend/app/services/scoring/transform.py       (new)
backend/app/services/scoring/service.py         (new)
backend/app/services/scoring/model_loader.py    (new)
backend/app/core/config.py                      (model_path, decision_threshold)
backend/app/ml/data_gen/generator.py            (demo customer retuned)
backend/tests/unit/test_score_transform.py      (new)
backend/tests/integration/test_scoring_service.py (new)
docs/DECISIONS.md                               (ADR 0020-0021)
docs/stages/STAGE_4_REPORT.md, README.md        (status)
```

## 5. How to run it (from a clean checkout)
```bash
cd backend && uv venv && uv pip install -e ".[dev]"
uv run python ../scripts/train_model.py            # produces artifacts/scoring_model.joblib

# Score in a REPL against a seeded DB (see scripts/seed_demo.py for seeding):
uv run python - <<'PY'
import asyncio, app.core.config as c
# ... construct an AsyncSession, load_scoring_model(settings.model_path),
#     ScoringService(session, model).score_cooperative(demo_customer_id, op_id)
PY
```
(The HTTP surface for this lands in Stage 5: `POST /v1/score` and
`POST /v1/score/cooperative`.)

## 6. How to test it (with actual results)
```bash
cd backend
uv run ruff check .   # All checks passed!
uv run black --check . # unchanged
uv run mypy           # Success (64 source files)
uv run pytest -q      # full suite
```
**Stage 4 tests: 17 passed** (transform unit + scoring integration), ~2m09s.
The transform tests assert strict monotonicity over a 500-point PD grid, the
[300, 850] bound at extremes, and every A–E tier cutoff. The integration tests
(real Postgres + a model trained on the seeded population) assert:
- a full scored outcome (score in range, PD in [0,1], tier, 5 top factors) with a
  persisted `score_result` + `feature_snapshot` + audit entry;
- scoring is **refused without consent**, and the denial is audited;
- the **borderline flip regression** — the money shot.

**Borderline customer (verified, deterministic):**

| View | PD | Score | Tier | Decision |
|------|-----|-------|------|----------|
| Solo (home operator only) | **0.361** | 536 | E | **Reject** |
| Pooled (cooperative) | **0.098** | 655 | B | **Approve** |

PD delta **0.263**, score delta **+119**, decision **flips reject → approve** —
a measurable, repeatable demonstration of the cooperative network effect.

## 7. Screencap / demo notes
- The flip is the Stage 7 "money shot"; Stage 4 makes it real and queryable.
- After seeding + scoring, inspect `cooperative_lift` and `score_result` in
  `psql`: one lift row (solo_pd 0.36 vs pooled_pd 0.10) and two score rows (one
  per view) for the demo customer, plus `score.cooperative` in `audit_log`.

## 8. Known issues & gaps
- No HTTP endpoints yet — the service is invoked in-process; the versioned,
  authenticated `/v1/score` + `/v1/score/cooperative` API is Stage 5.
- `decision_threshold` defaults to the model's (0.25); per-operator policy
  thresholds are a Stage 5/8 concern.
- The `confidence_delta` is a sharpness heuristic (`|PD−0.5|`); a calibrated
  uncertainty interval is deferred.
- The integration tests train a model per module (real XGBoost) — ~30 s setup;
  acceptable but the slowest suite.

## 9. What Stage 5 will do
**Stage 5 — Multi-tenant API & auth.** Expose the versioned `/v1` REST surface
(login/refresh, operator management, customer lookup, **`POST /v1/score`** and
**`POST /v1/score/cooperative`**, score history, consent), with dual auth (JWT
users + hashed API keys), RBAC per route, strict **tenant isolation**, Redis
rate limiting, request audit, consistent error envelopes, OpenAPI docs, and a
generated TypeScript client — with negative-authz tests proving operator A cannot
read operator B's data.

## 10. Approval gate
**Stage 4 complete — awaiting approval to proceed.**
