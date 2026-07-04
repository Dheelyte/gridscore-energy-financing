"""Scoring service: feature build, inference, score transform, cooperative lift."""

from __future__ import annotations

from app.services.scoring.model_loader import ModelNotTrainedError, load_scoring_model
from app.services.scoring.service import (
    ConsentRequiredError,
    CooperativeOutcome,
    CustomerNotFoundError,
    ScoreOutcome,
    ScoringService,
)
from app.services.scoring.transform import (
    is_approved,
    pd_to_score,
    pd_to_tier,
)

__all__ = [
    "ConsentRequiredError",
    "CooperativeOutcome",
    "CustomerNotFoundError",
    "ModelNotTrainedError",
    "ScoreOutcome",
    "ScoringService",
    "is_approved",
    "load_scoring_model",
    "pd_to_score",
    "pd_to_tier",
]
