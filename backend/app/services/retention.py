"""Data-retention purge.

Deletes **derived** artefacts older than a retention window — feature snapshots,
score results, and cooperative-lift rows — which are point-in-time, regenerable,
and the most privacy-sensitive computed records. The raw cooperative signal
(``repayment_event``) is retained for the model and pruned via partition
``DETACH`` in production; the immutable ``audit_log`` is never deleted (defence of
the audit trail). Idempotent and safe to retry.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CooperativeLift, FeatureSnapshot, ScoreResult


def _rowcount(result: Any) -> int:
    """DML statements return a CursorResult; ``rowcount`` is the rows affected."""
    return int(result.rowcount or 0)


@dataclass
class PurgeResult:
    cutoff: dt.datetime
    feature_snapshots: int
    score_results: int
    cooperative_lifts: int

    @property
    def total(self) -> int:
        return self.feature_snapshots + self.score_results + self.cooperative_lifts


async def purge_derived_data(session: AsyncSession, *, retention_days: int) -> PurgeResult:
    """Delete derived rows created before ``now - retention_days``."""
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=retention_days)

    snaps = await session.execute(
        delete(FeatureSnapshot).where(FeatureSnapshot.created_at < cutoff)
    )
    scores = await session.execute(delete(ScoreResult).where(ScoreResult.created_at < cutoff))
    lifts = await session.execute(
        delete(CooperativeLift).where(CooperativeLift.created_at < cutoff)
    )
    await session.flush()

    return PurgeResult(
        cutoff=cutoff,
        feature_snapshots=_rowcount(snaps),
        score_results=_rowcount(scores),
        cooperative_lifts=_rowcount(lifts),
    )
