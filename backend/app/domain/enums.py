"""Domain vocabulary — enumerations shared across models, services, and the API.

These live in ``domain`` (not ``db``) because they are part of the ubiquitous
language, independent of how they happen to be persisted. They are stored as
native PostgreSQL ENUM types (see the SQLAlchemy models).
"""

from __future__ import annotations

from enum import StrEnum


class OperatorStatus(StrEnum):
    """Lifecycle of a tenant (PAYG operator) in the cooperative."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class UserRole(StrEnum):
    """RBAC roles. Drives authorisation in Stage 5."""

    PLATFORM_ADMIN = "platform_admin"
    OPERATOR_ADMIN = "operator_admin"
    OPERATOR_ANALYST = "operator_analyst"
    LENDER_VIEWER = "lender_viewer"


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"
    INVITED = "invited"


class ConsentScope(StrEnum):
    """What a customer has consented to. Gates enrichment and scoring."""

    DATA_SHARING = "data_sharing"  # contribute repayment history to the cooperative
    ENRICHMENT = "enrichment"  # pull mobile-money/airtime/utility signals
    SCORING = "scoring"  # be scored by requesting operators


class RepaymentStatus(StrEnum):
    """Outcome of a single PAYG instalment."""

    PENDING = "pending"
    ON_TIME = "on_time"
    LATE = "late"
    DEFAULTED = "defaulted"


class ProviderType(StrEnum):
    """Enrichment signal source (port behind a swappable adapter)."""

    MOBILE_MONEY = "mobile_money"
    AIRTIME = "airtime"
    UTILITY = "utility"


class ScoreView(StrEnum):
    """The two cooperative views — the core differentiator.

    ``SOLO``   — features from the home operator's partial history only.
    ``POOLED`` — features from the full cooperative history.
    """

    SOLO = "solo"
    POOLED = "pooled"


class RiskTier(StrEnum):
    """Risk grade with documented PD cutoffs (defined in the scoring service)."""

    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class PromotionStage(StrEnum):
    """MLflow-style model registry stage."""

    NONE = "none"
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
