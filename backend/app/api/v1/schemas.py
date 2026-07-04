"""Request/response schemas for the v1 API (Pydantic v2)."""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    ConsentScope,
    OperatorStatus,
    RiskTier,
    ScoreView,
    UserRole,
)


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class Me(BaseModel):
    kind: str
    subject_id: UUID
    role: UserRole
    operator_id: UUID | None
    email: str | None = None


# ---- operators ----
class OperatorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    country: str = Field(min_length=2, max_length=2, description="ISO 3166-1 alpha-2")


class OperatorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    country: str
    status: OperatorStatus
    created_at: dt.datetime


class ApiKeyCreated(BaseModel):
    prefix: str
    api_key: str = Field(description="Full key, shown once. Store it securely.")
    note: str = "This is the only time the full key is shown."


# ---- users ----
class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    operator_id: UUID | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    role: UserRole
    operator_id: UUID | None


# ---- customers ----
class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    identity_hash: str
    home_operator_id: UUID
    created_at: dt.datetime


# ---- consent ----
class ConsentCreate(BaseModel):
    scope: ConsentScope
    granted: bool = True
    source: str = Field(default="api", max_length=80)
    expires_at: dt.datetime | None = None


class ConsentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    scope: ConsentScope
    granted: bool
    source: str
    granted_at: dt.datetime
    expires_at: dt.datetime | None


# ---- scoring ----
class ScoreRequest(BaseModel):
    customer_id: UUID
    view: ScoreView = ScoreView.POOLED


class CooperativeScoreRequest(BaseModel):
    customer_id: UUID


class TopFactorOut(BaseModel):
    feature: str
    label: str
    value: float
    contribution: float
    direction: str


class ScoreOut(BaseModel):
    customer_id: UUID
    view: ScoreView
    default_probability: float
    energy_credit_score: int
    risk_tier: RiskTier
    approved: bool
    model_version: str
    top_factors: list[TopFactorOut]


class CooperativeOut(BaseModel):
    customer_id: UUID
    solo: ScoreOut
    pooled: ScoreOut
    pd_delta: float
    confidence_delta: float
    score_delta: int
    decision_flips: bool
    lift_metric: float


class ScoreHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    view: ScoreView
    energy_credit_score: int
    default_probability: float
    risk_tier: RiskTier
    model_version: str
    created_at: dt.datetime
