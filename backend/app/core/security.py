"""Security primitives: password hashing, JWT tokens, and API-key handling.

* **Passwords** are hashed with Argon2id (memory-hard, modern default).
* **Human users** authenticate with a short-lived JWT *access* token plus a
  longer-lived *refresh* token (OAuth2 password flow).
* **Machine clients** authenticate with an API key of the form
  ``<prefix>.<secret>``. Only the SHA-256 of the secret is stored; the plaintext
  is shown once at creation and never again.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()

ACCESS_TOKEN_TTL = dt.timedelta(minutes=30)
REFRESH_TOKEN_TTL = dt.timedelta(days=7)
JWT_ALGORITHM = "HS256"

_API_KEY_PREFIX = "gsk"  # GridScore key


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


# --------------------------------------------------------------------------- #
# Passwords
# --------------------------------------------------------------------------- #
def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def create_token(
    *,
    subject: str,
    token_type: TokenType,
    secret_key: str,
    extra: dict[str, Any] | None = None,
    now: dt.datetime | None = None,
) -> str:
    now = now or dt.datetime.now(dt.UTC)
    ttl = ACCESS_TOKEN_TTL if token_type is TokenType.ACCESS else REFRESH_TOKEN_TTL
    payload: dict[str, Any] = {
        "sub": subject,
        "type": str(token_type),
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        **(extra or {}),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_token(token: str, *, secret_key: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` on any problem."""
    decoded: dict[str, Any] = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    return decoded


# --------------------------------------------------------------------------- #
# API keys
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class GeneratedApiKey:
    prefix: str  # public, indexed lookup handle
    secret: str  # plaintext, shown once
    hashed_secret: str  # stored
    full_key: str  # what the client uses: "<prefix>.<secret>"


def hash_api_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def generate_api_key() -> GeneratedApiKey:
    prefix = f"{_API_KEY_PREFIX}_{secrets.token_hex(4)}"
    secret = secrets.token_urlsafe(32)
    return GeneratedApiKey(
        prefix=prefix,
        secret=secret,
        hashed_secret=hash_api_secret(secret),
        full_key=f"{prefix}.{secret}",
    )


def split_api_key(full_key: str) -> tuple[str, str] | None:
    """Split ``<prefix>.<secret>``; return None if malformed."""
    prefix, sep, secret = full_key.partition(".")
    if not sep or not prefix or not secret:
        return None
    return prefix, secret
