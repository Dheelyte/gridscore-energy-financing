"""Operator (tenant) management — platform-admin only."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import ConflictError, NotFoundError
from app.api.v1.deps import Principal, get_session, require_roles
from app.api.v1.schemas import (
    ApiKeyCreated,
    OperatorCreate,
    OperatorOut,
    UserCreate,
    UserOut,
)
from app.core.security import generate_api_key, hash_password
from app.db.models import ApiCredential, Operator, UserAccount
from app.db.repositories import (
    ApiCredentialRepository,
    OperatorRepository,
    UserAccountRepository,
)
from app.domain.enums import OperatorStatus, UserRole, UserStatus

router = APIRouter(prefix="/operators", tags=["operators"])

_admin_only = require_roles(UserRole.PLATFORM_ADMIN)


@router.post("", response_model=OperatorOut, status_code=201, summary="Onboard an operator")
async def create_operator(
    body: OperatorCreate,
    _: Principal = Depends(_admin_only),
    session: AsyncSession = Depends(get_session),
) -> Operator:
    repo = OperatorRepository(session)
    if await repo.get_by_name(body.name) is not None:
        raise ConflictError("An operator with that name already exists.")
    return await repo.add(
        Operator(name=body.name, country=body.country.upper(), status=OperatorStatus.ACTIVE)
    )


@router.get("", response_model=list[OperatorOut], summary="List operators")
async def list_operators(
    _: Principal = Depends(_admin_only),
    session: AsyncSession = Depends(get_session),
) -> list[Operator]:
    return await OperatorRepository(session).list(limit=200)


@router.post(
    "/{operator_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=201,
    summary="Issue a machine API key for an operator",
)
async def issue_api_key(
    operator_id: UUID,
    _: Principal = Depends(_admin_only),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreated:
    if await OperatorRepository(session).get(operator_id) is None:
        raise NotFoundError("Operator not found.")
    key = generate_api_key()
    await ApiCredentialRepository(session).add(
        ApiCredential(
            operator_id=operator_id,
            key_prefix=key.prefix,
            hashed_secret=key.hashed_secret,
            scopes=["score:read"],
        )
    )
    return ApiKeyCreated(prefix=key.prefix, api_key=key.full_key)


@router.post(
    "/users",
    response_model=UserOut,
    status_code=201,
    summary="Create a user account",
)
async def create_user(
    body: UserCreate,
    _: Principal = Depends(_admin_only),
    session: AsyncSession = Depends(get_session),
) -> UserAccount:
    repo = UserAccountRepository(session)
    if await repo.get_by_email(body.email) is not None:
        raise ConflictError("A user with that email already exists.")
    return await repo.add(
        UserAccount(
            email=body.email,
            hashed_password=hash_password(body.password),
            role=body.role,
            operator_id=body.operator_id,
            status=UserStatus.ACTIVE,
        )
    )
