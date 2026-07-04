#!/usr/bin/env python
"""Train the GridScore default-risk model, register it, and write its model card.

    python scripts/train_model.py
    python scripts/train_model.py --customers 4000 --seed 7

Logs the run to a local MLflow (sqlite) registry, saves a ScoringModel bundle for
the scoring service (Stage 4), and regenerates docs/model_cards/. All data is
synthetic.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.ml.data_gen.config import GeneratorConfig  # noqa: E402
from app.ml.data_gen.generator import SyntheticGenerator  # noqa: E402
from app.ml.model_card import render_model_card  # noqa: E402
from app.ml.training import train  # noqa: E402

DEFAULT_MODEL_PATH = BACKEND_DIR / "artifacts" / "scoring_model.joblib"
DEFAULT_CARD_PATH = REPO_ROOT / "docs" / "model_cards" / "energy-credit-score.md"
DEFAULT_TRACKING_URI = f"sqlite:///{BACKEND_DIR / 'mlruns' / 'mlflow.db'}"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train + register the GridScore model.")
    p.add_argument("--customers", type=int, default=4000)
    p.add_argument("--seed", type=int, default=GeneratorConfig().seed)
    p.add_argument("--tracking-uri", default=DEFAULT_TRACKING_URI)
    p.add_argument("--model-out", type=Path, default=DEFAULT_MODEL_PATH)
    p.add_argument("--card-out", type=Path, default=DEFAULT_CARD_PATH)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    (BACKEND_DIR / "mlruns").mkdir(parents=True, exist_ok=True)

    config = GeneratorConfig(n_customers=args.customers, seed=args.seed)
    population = SyntheticGenerator(config).generate()
    result = train(population, tracking_uri=args.tracking_uri)

    saved = result.model.save(args.model_out)
    card = render_model_card(
        result, n_customers=config.n_customers, base_rate=population.default_rate
    )
    args.card_out.parent.mkdir(parents=True, exist_ok=True)
    args.card_out.write_text(card, encoding="utf-8")

    m = result.metrics
    print("\n=== GridScore model trained (SYNTHETIC DATA) ===")
    print(f"  registered version .. {result.model_version}  (run {result.run_id[:12]})")
    print(f"  ROC-AUC ............. {m['roc_auc']:.3f}  (target 0.70-0.82)")
    print(f"  PR-AUC .............. {m['pr_auc']:.3f}")
    print(f"  Brier (cal/uncal) ... {m['brier']:.4f} / {m['brier_uncalibrated']:.4f}")
    print(f"  leakage warning ..... {result.leakage_warning}")
    print("  top features ........ " + ", ".join(list(result.feature_importances)[:3]))
    print(f"  bundle .............. {saved}")
    print(f"  model card .......... {args.card_out}")
    print()


if __name__ == "__main__":
    main()
