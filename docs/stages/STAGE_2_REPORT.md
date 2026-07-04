# Stage 2 Report — Synthetic Data Engine

## 1. Stage name & objective
**Stage 2 — Synthetic data engine (credibility foundation).** Build a
configurable generator that produces realistic cooperative PAYG data with
*genuine* predictive structure: default is a real logistic function of the
Appendix A features plus **irreducible noise**, yielding a ~10–20% base default
rate and an honest (not perfect) achievable AUC. Model the **cooperative split**
(home operator + a degraded *solo* slice vs the full *pooled* history), persist
everything through the Stage 1 schema, ship a repeatable `scripts/seed_demo.py`
containing a curated borderline customer who flips reject→approve under the
pooled view, and prove the statistics with tests.

## 2. What was built
- **Canonical feature schema** (`app/ml/feature_schema.py`) — the nine Appendix A
  features with labels, ranges, and risk directions, as the single source of
  truth shared by the generator, the Stage 3 model, and the explanations UI.
- **Generator** (`app/ml/data_gen/`):
  - `config.py` — `GeneratorConfig` (seed, N, operator roster, target rate,
    `signal_scale`, `logit_noise_sd`, cross-operator/no-consent fractions) and
    the logistic `DEFAULT_COEFFICIENTS` encoding the thesis (repayment rate &
    prior defaults strongest).
  - `generator.py` — `SyntheticGenerator`: latent reliability → nine correlated
    features → **calibrated logistic label with irreducible noise** → raw
    `repayment_event` / `enrichment_signal` / consent records split across
    operators. Deterministic (seeded). Includes a rank-based AUC helper and the
    **curated borderline demo customer**.
  - `persistence.py` — `SyntheticDataWriter`: bulk-insert the population through
    the Stage 1 models; `reset()` truncates for idempotent reseeds.
  - `seed.py` — reusable `seed_population()` orchestration.
- **Synthetic ground-truth table** — `SyntheticCustomerProfile` model +
  **migration 0002** (`synthetic_customer_profile`): stores the true label, true
  PD, latent features, and demo flags. Separate from production tables and empty
  in production (honesty posture).
- **Seed CLI** — `scripts/seed_demo.py` with `--customers/--seed/--no-reset`,
  printing a labelled-synthetic summary (rate, AUC ceiling, demo customer).
- **Migration immutability fix** — 0001 now pins its table set by name so adding
  a later model never changes what it creates.
- **Tests** — 8 generator unit tests (no DB) + 4 seeding integration tests
  (testcontainers).

## 3. Key decisions & trade-offs
New ADRs in [`docs/DECISIONS.md`](../DECISIONS.md):
- **ADR-0013** — honest predictive structure: irreducible label noise + a
  documented `signal_scale` so the achievable (Bayes) AUC is ~0.80, not ~0.98,
  and the label is not recoverable from the repayment history (no leakage).
- **ADR-0014** — synthetic ground truth lives in a separate `synthetic_*` table,
  empty in production.

The central trade-off was **calibrating realism**. My first model baked the noise
into the probability the label was sampled from, which made the data almost
perfectly separable (Bayes-AUC ≈ 0.98 — a leakage smell). I corrected the model
so the noise perturbs the *label* but is invisible to the features, then tuned
`signal_scale` empirically (full-scale signal std ≈ 5.0 → far too separable) down
to 0.26, landing a Bayes ceiling of ~0.80 and a quick logistic-on-observed-
features AUC of ~0.79 — comfortably inside the Appendix A target.

## 4. File tree delta
```
backend/pyproject.toml                                   (numpy dep)
backend/uv.lock                                          (updated)
backend/app/ml/feature_schema.py                         (new)
backend/app/ml/data_gen/__init__.py                      (new)
backend/app/ml/data_gen/config.py                        (new)
backend/app/ml/data_gen/generator.py                     (new)
backend/app/ml/data_gen/persistence.py                   (new)
backend/app/ml/data_gen/seed.py                          (new)
backend/app/db/models/synthetic.py                       (new)
backend/app/db/models/__init__.py                        (+ SyntheticCustomerProfile)
backend/app/db/migrations/versions/0002_synthetic_profile.py (new)
backend/app/db/migrations/versions/0001_initial.py       (pin revision tables)
backend/tests/unit/test_synthetic_generator.py           (new)
backend/tests/integration/test_seed_demo.py              (new)
backend/tests/integration/test_migrations.py             (table count 62→63)
scripts/seed_demo.py                                     (new)
docs/{DATA_MODEL,DECISIONS,RUNBOOK,ARCHITECTURE}.md, README.md (updates)
```

## 5. How to run it (from a clean checkout)
```bash
cp .env.example .env
cd backend && uv venv && uv pip install -e ".[dev]"
docker compose -f ../infra/docker-compose.yml up -d postgres
GRIDSCORE_DATABASE_URL=postgresql+asyncpg://gridscore:gridscore@localhost:5432/gridscore \
  uv run alembic upgrade head
GRIDSCORE_DATABASE_URL=postgresql+asyncpg://gridscore:gridscore@localhost:5432/gridscore \
  uv run python ../scripts/seed_demo.py
```

**Observed seed output (default config, 2000 customers):**
```
operators .......... 5          repayment events ... 23,941
customers .......... 2001       enrichment signals . 6003
base default rate .. 15.6%  (target 10–20%)
feature-AUC ceiling  0.800
borderline demo: solo on-time 33% vs pooled on-time 92%
156 customers have no scoring consent (consent gating will matter in Stage 4)
```

## 6. How to test it (with actual results)
```bash
cd backend
uv run ruff check .   # All checks passed!
uv run black --check . # 49 files unchanged
uv run mypy            # Success: no issues found in 49 source files
uv run pytest -p no:cacheprovider --cov=app --cov-report=term-missing
```
**Result: 34 passed (15 unit + 19 integration), coverage 93%.** New coverage:
- **Generator (unit, no DB):** base default rate ∈ [0.10, 0.20]; achievable
  **Bayes-AUC ∈ [0.72, 0.86]** (honest, not perfect); feature values within
  schema ranges; **`payg_repayment_rate` and `prior_defaults` are the two
  strongest signals** with correct directions (the thesis); **no leakage** (some
  defaulters still have >0.8 observed on-time rate); determinism under a fixed
  seed; some customers lack scoring consent; and the **borderline demo customer**
  setup (solo on-time <0.5, pooled >0.85, no defaults).
- **Seeding (integration, real Postgres):** all tables populated with correct
  counts; persisted default rate in range; the demo customer present with
  `is_demo`/`scenario` and a strictly larger pooled-vs-solo history; reseed is
  idempotent via `reset()`.

## 7. Screencap / demo notes
- Run the seeder and read the printed summary — the **15.6% default rate**, the
  **0.800 AUC ceiling**, and the demo customer's **33% solo vs 92% pooled**
  on-time rates are the headline credibility numbers.
- In `psql`: `SELECT default_label, count(*) FROM synthetic_customer_profile
  GROUP BY 1;` shows the labelled-synthetic ground truth; the borderline customer
  is `WHERE scenario = 'borderline_flip'`.
- The visual money-shot (the score flip itself) is rendered in Stage 7; Stage 2
  guarantees the data underneath it.

## 8. Known issues & gaps
- **No model yet** — the reject→approve *decision* flip is realised by the
  scoring service in Stage 4; Stage 2 only guarantees the structural setup
  (solo history looks risky, pooled looks safe). The reported ~0.79 trained AUC
  is from a quick logistic probe, not the Stage 3 XGBoost model.
- **Currency is simplified** — instalment amounts are USD-equivalent with an
  informational local `currency` code, so `loan_to_income` stays consistent.
- **Fixed anchor month (May 2026)** keeps histories inside the 2023–2026
  partition window; very long histories are clamped at the window's lower bound.
- Generation is single-process and in-memory; at the default 2000 customers it
  runs in ~10–15s including engine startup. Much larger runs would want batched
  inserts/streaming (not needed for the demo).

## 9. What Stage 3 will do
**Stage 3 — ML platform.** Build the deterministic feature-engineering pipeline
(raw events/signals → the nine-feature vector, in **solo** and **pooled**
variants) reused for training and inference; a training pipeline with
train/test split, class-imbalance handling, and calibration logged to **MLflow**
with a versioned, stage-promotable registered model; evaluation reporting
ROC-AUC, PR-AUC, Brier score, and a confusion matrix (targeting ~0.70–0.82 and
flagging anything suspiciously high); **SHAP** explanations with human-readable
top factors; an auto-generated **model card**; and a **PSI drift monitor** — all
trained on the data this stage produced.

## 10. Approval gate
**Stage 2 complete — awaiting approval to proceed.**
