"""Boundary anonymisation: salted hashing, normalisation, and PII safety."""

from __future__ import annotations

import pytest

from app.services.ingestion.anonymise import hash_identity, normalise_identifier

pytestmark = pytest.mark.unit

_SALT = "unit-test-salt"


def test_hash_is_deterministic_and_64_hex() -> None:
    h1 = hash_identity("+254700123456", salt=_SALT)
    h2 = hash_identity("+254700123456", salt=_SALT)
    assert h1 == h2
    assert len(h1) == 64 and all(c in "0123456789abcdef" for c in h1)


def test_normalisation_collapses_formatting() -> None:
    assert normalise_identifier("+254 700-123 456") == "254700123456"
    assert hash_identity("+254 700-123 456", salt=_SALT) == hash_identity(
        "254700123456", salt=_SALT
    )


def test_salt_changes_the_hash() -> None:
    assert hash_identity("ID-123", salt="a") != hash_identity("ID-123", salt="b")


def test_raw_value_is_not_recoverable_from_hash() -> None:
    raw = "+254700123456"
    h = hash_identity(raw, salt=_SALT)
    assert raw not in h
    assert "254700123456" not in h


def test_empty_identifier_rejected() -> None:
    with pytest.raises(ValueError):
        hash_identity("   ", salt=_SALT)
