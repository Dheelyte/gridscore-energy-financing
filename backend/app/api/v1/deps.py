"""Shared API dependencies: authentication, RBAC, tenancy, rate limiting.

Two authentication schemes resolve to a single :class:`Principal`:

* ``Authorization: Bearer <jwt>`` — a human user (OAuth2 password flow).
* ``X-API-Key: <prefix>.<secret>`` — a machine client bound to an operator.

Authorization is then enforced per-route with :func:`require_roles`, and
**tenant isolation** with :func:`ensure_customer_access` — an operator can only
ever touch its own customers (platform admins are unrestricted).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

import jwt
from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import (
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ServiceUnavailableError,
)
from app.core.config import Settings
from app.core.ratelimit import RateLimiter
from app.core.security import TokenType, decode_token, hash_api_secret, split_api_key
from app.db.models import Customer
from app.db.repositories import ApiCredentialRepository, UserAccountRepository
from app.db.session import get_session
from app.domain.enums import UserRole
from app.ml.model import ScoringModel

__all__ = [
    "Principal",
    "ensure_customer_access",
    "get_principal",
    "get_scoring_model",
    "get_session",
    "get_settings_dep",
    "rate_limit",
    "require_roles",
]


@dataclass(frozen=True)
class Principal:
    kind: str  # "user" | "api_key"
    subject_id: UUID
    role: UserRole
    operator_id: UUID | None
    email: str | None = None

    @property
    def is_platform_admin(self) -> bool:
        return self.role is UserRole.PLATFORM_ADMIN

    def label(self) -> str:
        return f"{self.kind}:{self.subject_id}"


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_scoring_model(request: Request) -> ScoringModel:
    model: ScoringModel | None = getattr(request.app.state, "scoring_model", None)
    if model is None:
        raise ServiceUnavailableError(
            "Scoring model is not loaded. Train one with scripts/train_model.py."
        )
    return model


async def get_principal(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Principal:
    settings: Settings = request.app.state.settings

    api_key = request.headers.get("x-api-key")
    if api_key:
        return await _principal_from_api_key(api_key, session)

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return await _principal_from_jwt(auth[7:].strip(), session, settings)

    raise AuthenticationError("Missing credentials (Bearer token or X-API-Key).")


async def _principal_from_jwt(token: str, session: AsyncSession, settings: Settings) -> Principal:
    try:
        payload = decode_token(token, secret_key=settings.secret_key.get_secret_value())
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired token.") from exc
    if payload.get("type") != TokenType.ACCESS.value:
        raise AuthenticationError("Expected an access token.")

    user = await UserAccountRepository(session).get(UUID(str(payload["sub"])))
    if user is None or user.status.value == "disabled":
        raise AuthenticationError("User not found or disabled.")
    return Principal(
        kind="user",
        subject_id=user.id,
        role=user.role,
        operator_id=user.operator_id,
        email=user.email,
    )


async def _principal_from_api_key(api_key: str, session: AsyncSession) -> Principal:
    parts = split_api_key(api_key)
    if parts is None:
        raise AuthenticationError("Malformed API key.")
    prefix, secret = parts
    cred = await ApiCredentialRepository(session).get_by_prefix(prefix)
    if cred is None or cred.revoked or cred.hashed_secret != hash_api_secret(secret):
        raise AuthenticationError("Invalid API key.")
    cred.last_used_at = dt.datetime.now(dt.UTC)
    # Machine clients act with analyst-level read/score scope for their operator.
    return Principal(
        kind="api_key",
        subject_id=cred.id,
        role=UserRole.OPERATOR_ANALYST,
        operator_id=cred.operator_id,
    )


def require_roles(*roles: UserRole) -> Callable[[Principal], Awaitable[Principal]]:
    """Dependency factory enforcing that the principal holds one of ``roles``."""

    async def _dep(principal: Principal = Depends(get_principal)) -> Principal:
        if principal.role not in roles:
            raise AuthorizationError(
                "Insufficient role.",
                details={"required": [str(r) for r in roles], "actual": str(principal.role)},
            )
        return principal

    return _dep


def ensure_customer_access(principal: Principal, customer: Customer) -> None:
    """Tenant isolation: operators may only access their own customers.

    Returns 404 (not 403) cross-tenant so existence is not leaked."""
    if principal.is_platform_admin:
        return
    if principal.operator_id is None or customer.home_operator_id != principal.operator_id:
        raise NotFoundError("Customer not found.")


def rate_limit(limit: int, window_seconds: int = 60) -> Callable[..., Awaitable[None]]:
    """Dependency factory: per-principal fixed-window rate limit."""

    async def _dep(
        request: Request,
        response: Response,
        principal: Principal = Depends(get_principal),
    ) -> None:
        limiter = RateLimiter(request.app.state.redis, limit=limit, window_seconds=window_seconds)
        decision = await limiter.hit(principal.label())
        for key, value in decision.headers().items():
            response.headers[key] = value
        if not decision.allowed:
            raise RateLimitError(
                "Rate limit exceeded.",
                headers=decision.headers(),
                details={"limit": limit, "window_seconds": window_seconds},
            )

    return _dep
