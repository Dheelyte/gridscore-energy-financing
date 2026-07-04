"""Authentication endpoints: OAuth2 password login, token refresh, and identity."""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import AuthenticationError
from app.api.v1.deps import Principal, get_principal, get_session, get_settings_dep
from app.api.v1.schemas import Me, RefreshRequest, Token
from app.core.config import Settings
from app.core.security import TokenType, create_token, decode_token, verify_password
from app.db.repositories import UserAccountRepository

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id: str, secret_key: str) -> Token:
    return Token(
        access_token=create_token(
            subject=user_id, token_type=TokenType.ACCESS, secret_key=secret_key
        ),
        refresh_token=create_token(
            subject=user_id, token_type=TokenType.REFRESH, secret_key=secret_key
        ),
    )


@router.post("/login", response_model=Token, summary="Log in (OAuth2 password flow)")
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> Token:
    user = await UserAccountRepository(session).get_by_email(form.username)
    if user is None or not verify_password(form.password, user.hashed_password):
        raise AuthenticationError("Incorrect email or password.")
    return _issue_tokens(str(user.id), settings.secret_key.get_secret_value())


@router.post("/refresh", response_model=Token, summary="Exchange a refresh token")
async def refresh(
    body: RefreshRequest,
    settings: Settings = Depends(get_settings_dep),
) -> Token:
    secret = settings.secret_key.get_secret_value()
    try:
        payload = decode_token(body.refresh_token, secret_key=secret)
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid or expired refresh token.") from exc
    if payload.get("type") != TokenType.REFRESH.value:
        raise AuthenticationError("Expected a refresh token.")
    return _issue_tokens(str(payload["sub"]), secret)


@router.get("/me", response_model=Me, summary="Current principal")
async def me(principal: Principal = Depends(get_principal)) -> Me:
    return Me(
        kind=principal.kind,
        subject_id=principal.subject_id,
        role=principal.role,
        operator_id=principal.operator_id,
        email=principal.email,
    )
