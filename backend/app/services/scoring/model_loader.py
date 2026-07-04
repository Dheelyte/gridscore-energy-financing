"""Load the serialised ScoringModel bundle for the scoring service.

The bundle is produced by ``scripts/train_model.py``. Loading is cached so the
(relatively large) model is deserialised once per process.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.ml.model import ScoringModel


class ModelNotTrainedError(RuntimeError):
    """Raised when no model bundle exists at the configured path."""


@lru_cache(maxsize=4)
def load_scoring_model(path: str) -> ScoringModel:
    """Load and cache a ScoringModel from ``path``."""
    bundle = Path(path)
    if not bundle.exists():
        raise ModelNotTrainedError(
            f"No model bundle at {bundle}. Run: python scripts/train_model.py"
        )
    return ScoringModel.load(bundle)
