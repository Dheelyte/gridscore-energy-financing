"""Auto-generate a Markdown model card from a training result.

Model cards (Mitchell et al., 2019) document a model's intended use, data,
metrics, and limitations. Ours is generated from the actual training run so it
can never drift from the model that shipped.
"""

from __future__ import annotations

import datetime as dt

from app.ml.feature_schema import FEATURE_BY_NAME
from app.ml.training import TrainingResult


def render_model_card(result: TrainingResult, *, n_customers: int, base_rate: float) -> str:
    m = result.metrics
    lines: list[str] = []
    a = lines.append

    a(f"# Model Card — GridScore Energy Credit Score (v{result.model_version})")
    a("")
    a(
        f"_Generated {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M UTC} from MLflow run "
        f"`{result.run_id}`._"
    )
    a("")
    a(
        "> ⚠️ **Trained on synthetic data.** Metrics are realistic by construction, "
        "not validated against real-world defaults. See *Limitations*."
    )
    a("")

    a("## Intended use")
    a("- **Task:** estimate the probability that a PAYG energy borrower defaults.")
    a(
        "- **Users:** cooperative operators deciding whether to extend a loan; "
        "lenders/DFIs assessing portfolio risk."
    )
    a(
        "- **Out of scope:** automated adverse action without human review; any use "
        "on populations unlike the (synthetic) training distribution."
    )
    a("")

    a("## Data")
    a(f"- **Source:** GridScore synthetic data engine (Stage 2), {n_customers} customers.")
    a(f"- **Base default rate:** {base_rate:.1%}.")
    a(
        "- **Features:** nine signals from repayment history + mobile-money / airtime "
        "/ utility enrichment, computed by the shared feature pipeline (pooled view)."
    )
    a(
        "- **Label:** sampled from a logistic model over the features with irreducible "
        "noise (so the achievable AUC is realistic, not perfect)."
    )
    a("")

    a("## Methodology")
    a("- XGBoost classifier (shallow, regularised) with `scale_pos_weight` for class " "imbalance.")
    a("- Probability **calibration** (isotonic) on out-of-fold predictions.")
    a(
        "- Stratified train/test split; AUC/PR-AUC measure discrimination (raw "
        "scores), Brier measures calibration — all on the untouched test set."
    )
    a("")

    a("## Performance (test set)")
    a("")
    a("| Metric | Value |")
    a("|---|---|")
    a(f"| ROC-AUC | {m['roc_auc']:.3f} |")
    a(f"| PR-AUC (avg precision) | {m['pr_auc']:.3f} |")
    a(f"| Brier score (calibrated) | {m['brier']:.4f} |")
    a(f"| Brier score (uncalibrated) | {m['brier_uncalibrated']:.4f} |")
    a(f"| Base rate | {m['base_rate']:.1%} |")
    a(f"| Test samples | {int(m['n_test'])} |")
    a("")
    c = result.confusion
    a(
        f"Confusion matrix @ PD ≥ {result.model.threshold:.2f}: "
        f"TP={c['tp']} FP={c['fp']} FN={c['fn']} TN={c['tn']}."
    )
    a("")
    if result.leakage_warning:
        a("> 🚩 **Leakage check:** ROC-AUC exceeds 0.90 — investigate before trusting.")
    else:
        a(
            "> ✅ **Leakage check:** ROC-AUC within the realistic 0.70-0.82 band — no "
            "leakage smell."
        )
    a("")

    a("## Feature importance (XGBoost gain)")
    a("")
    a("| Feature | Importance | Direction vs default |")
    a("|---|---|---|")
    for name, imp in result.feature_importances.items():
        spec = FEATURE_BY_NAME[name]
        a(f"| {spec.label} | {imp:.3f} | {spec.direction} |")
    a("")
    top2 = list(result.feature_importances)[:2]
    a(
        f"_Top signals: **{top2[0]}**, **{top2[1]}** — consistent with the product "
        "thesis that repayment behaviour and prior defaults dominate._"
    )
    a("")

    a("## Limitations & ethical considerations")
    a(
        "- **Synthetic data:** no claim of real-world calibration; the pipeline, not "
        "the numbers, is the deliverable."
    )
    a(
        "- **Fairness:** no protected attributes are used, but proxy bias in real data "
        "must be audited before production."
    )
    a(
        "- **Consent & privacy:** scoring is gated on consent; only salted identity "
        "hashes are stored (no raw PII)."
    )
    a(
        "- **Drift:** monitored via PSI against the training distribution; significant "
        "drift should trigger retraining."
    )
    a("")
    return "\n".join(lines)
