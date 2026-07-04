"""Anonymisation at the ingestion boundary.

A customer is identified only by a **salted SHA-256** of a national ID or phone
number. The raw identifier is hashed here, at the edge, and **never persisted** —
this is the privacy invariant the whole platform rests on. Normalisation (strip
whitespace, lower-case) makes the hash stable across formatting differences.
"""

from __future__ import annotations

import hashlib
import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise_identifier(raw: str) -> str:
    """Canonicalise a raw identifier so trivial formatting differences (spaces,
    dashes, casing, a leading +) map to the same person."""
    return _NON_ALNUM.sub("", raw.strip().lower())


def hash_identity(raw_identifier: str, *, salt: str) -> str:
    """Salted SHA-256 of a normalised identifier (64-char hex). Deterministic for
    a given salt so the same person resolves to one cooperative record."""
    if not raw_identifier or not raw_identifier.strip():
        raise ValueError("raw_identifier must be non-empty")
    normalised = normalise_identifier(raw_identifier)
    if not normalised:
        raise ValueError("raw_identifier has no usable characters")
    return hashlib.sha256(f"{salt}:{normalised}".encode()).hexdigest()
