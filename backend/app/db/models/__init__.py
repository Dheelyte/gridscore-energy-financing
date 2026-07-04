"""ORM models. Importing this package registers every table on ``Base.metadata``
(relied on by Alembic autogenerate and by ``create_all`` in tests)."""

from __future__ import annotations

from app.db.base import Base
from app.db.models.customer import ConsentRecord, Customer
from app.db.models.events import EnrichmentSignal, RepaymentEvent
from app.db.models.platform import AuditLog, ModelVersion
from app.db.models.scoring import CooperativeLift, FeatureSnapshot, ScoreResult
from app.db.models.synthetic import SyntheticCustomerProfile
from app.db.models.tenancy import ApiCredential, Operator, UserAccount

__all__ = [
    "ApiCredential",
    "AuditLog",
    "Base",
    "ConsentRecord",
    "CooperativeLift",
    "Customer",
    "EnrichmentSignal",
    "FeatureSnapshot",
    "ModelVersion",
    "Operator",
    "RepaymentEvent",
    "ScoreResult",
    "SyntheticCustomerProfile",
    "UserAccount",
]
