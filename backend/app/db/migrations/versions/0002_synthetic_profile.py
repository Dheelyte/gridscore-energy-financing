"""synthetic_customer_profile (synthetic-only ground truth)

Revision ID: 0002_synthetic_profile
Revises: 0001_initial
Create Date: 2026-06-20

Adds the synthetic ground-truth table used by the Stage 2 data engine. Created
from the model metadata (a standard, non-partitioned table) to stay in lock-step
with the ORM — same approach as the bulk of 0001.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.db.models import Base

# revision identifiers, used by Alembic.
revision: str = "0002_synthetic_profile"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = Base.metadata.tables["synthetic_customer_profile"]


def upgrade() -> None:
    from alembic import op

    _TABLE.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    from alembic import op

    _TABLE.drop(bind=op.get_bind(), checkfirst=True)
