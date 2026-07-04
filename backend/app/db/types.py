"""Custom database types and ID generation.

UUIDv7 gives us time-ordered, globally-unique primary keys: random enough to be
unguessable, but with a leading millisecond timestamp so rows insert in roughly
chronological order — which keeps B-tree indexes and the monthly partitions of
``repayment_event`` healthy (far less page churn than fully-random UUIDv4).

Python 3.12's stdlib has no ``uuid7``; we implement the RFC 9562 layout here
rather than pull a native dependency.
"""

from __future__ import annotations

import os
import time
from uuid import UUID

_VERSION = 0x7
_VARIANT = 0b10


def uuid7() -> UUID:
    """Generate a UUIDv7 (RFC 9562).

    128-bit layout (most-significant first):
        unix_ts_ms (48) | version (4) | rand_a (12) | variant (2) | rand_b (62)
    """
    unix_ms = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10), "big")  # 80 random bits
    rand_a = rand & 0xFFF  # 12 bits
    rand_b = (rand >> 12) & ((1 << 62) - 1)  # 62 bits

    value = (unix_ms & 0xFFFF_FFFF_FFFF) << 80
    value |= _VERSION << 76
    value |= rand_a << 64
    value |= _VARIANT << 62
    value |= rand_b
    return UUID(int=value)


def uuid7_timestamp_ms(value: UUID) -> int:
    """Extract the embedded Unix-millisecond timestamp from a UUIDv7."""
    return value.int >> 80
