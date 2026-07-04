"""Repository layer — the app's data-access surface."""

from __future__ import annotations

from app.db.repositories.base import BaseRepository
from app.db.repositories.repositories import (
    ApiCredentialRepository,
    AuditLogRepository,
    ConsentRecordRepository,
    CooperativeLiftRepository,
    CustomerRepository,
    EnrichmentSignalRepository,
    FeatureSnapshotRepository,
    ModelVersionRepository,
    OperatorRepository,
    RepaymentEventRepository,
    ScoreResultRepository,
    UserAccountRepository,
)

__all__ = [
    "ApiCredentialRepository",
    "AuditLogRepository",
    "BaseRepository",
    "ConsentRecordRepository",
    "CooperativeLiftRepository",
    "CustomerRepository",
    "EnrichmentSignalRepository",
    "FeatureSnapshotRepository",
    "ModelVersionRepository",
    "OperatorRepository",
    "RepaymentEventRepository",
    "ScoreResultRepository",
    "UserAccountRepository",
]
