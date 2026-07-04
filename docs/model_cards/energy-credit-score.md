# Model Card — GridScore Energy Credit Score (v1)

_Generated 2026-06-27 10:02 UTC from MLflow run `1d38268d6fcb46dbb122c9536981cbb8`._

> ⚠️ **Trained on synthetic data.** Metrics are realistic by construction, not validated against real-world defaults. See *Limitations*.

## Intended use
- **Task:** estimate the probability that a PAYG energy borrower defaults.
- **Users:** cooperative operators deciding whether to extend a loan; lenders/DFIs assessing portfolio risk.
- **Out of scope:** automated adverse action without human review; any use on populations unlike the (synthetic) training distribution.

## Data
- **Source:** GridScore synthetic data engine (Stage 2), 4000 customers.
- **Base default rate:** 14.8%.
- **Features:** nine signals from repayment history + mobile-money / airtime / utility enrichment, computed by the shared feature pipeline (pooled view).
- **Label:** sampled from a logistic model over the features with irreducible noise (so the achievable AUC is realistic, not perfect).

## Methodology
- XGBoost classifier (shallow, regularised) with `scale_pos_weight` for class imbalance.
- Probability **calibration** (isotonic) on out-of-fold predictions.
- Stratified train/test split; AUC/PR-AUC measure discrimination (raw scores), Brier measures calibration — all on the untouched test set.

## Performance (test set)

| Metric | Value |
|---|---|
| ROC-AUC | 0.774 |
| PR-AUC (avg precision) | 0.464 |
| Brier score (calibrated) | 0.1044 |
| Brier score (uncalibrated) | 0.1438 |
| Base rate | 14.8% |
| Test samples | 1001 |

Confusion matrix @ PD ≥ 0.25: TP=64 FP=75 FN=84 TN=778.

> ℹ️ This matrix is from the original training run at a 0.25 boundary. The runtime
> approve/reject threshold has since been set to **0.12** (near the base default
> rate — approve only below-average-risk borrowers; see `app.core.config`); this
> matrix refreshes to the new boundary on the next `scripts/train_model.py` run.

> ✅ **Leakage check:** ROC-AUC within the realistic 0.70-0.82 band — no leakage smell.

## Feature importance (XGBoost gain)

| Feature | Importance | Direction vs default |
|---|---|---|
| PAYG on-time repayment rate | 0.226 | decreases |
| Prior defaults on record | 0.176 | increases |
| Utility payment consistency | 0.107 | decreases |
| Mobile-money inflow stability | 0.097 | decreases |
| Airtime top-up regularity | 0.096 | decreases |
| Loan-to-income ratio | 0.079 | increases |
| Length of PAYG history | 0.079 | decreases |
| Average monthly mobile-money inflow | 0.076 | decreases |
| Customer tenure | 0.064 | decreases |

_Top signals: **payg_repayment_rate**, **prior_defaults** — consistent with the product thesis that repayment behaviour and prior defaults dominate._

## Limitations & ethical considerations
- **Synthetic data:** no claim of real-world calibration; the pipeline, not the numbers, is the deliverable.
- **Fairness:** no protected attributes are used, but proxy bias in real data must be audited before production.
- **Consent & privacy:** scoring is gated on consent; only salted identity hashes are stored (no raw PII).
- **Drift:** monitored via PSI against the training distribution; significant drift should trigger retraining.
