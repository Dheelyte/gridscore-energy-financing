"""initial schema — tenancy, customers, events, scoring, platform

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-19

Design notes
------------
The standard (non-partitioned) tables are created from the application's
``Base.metadata`` so the migrated schema cannot drift from the ORM models —
there is one source of truth. The ``repayment_event`` table needs DDL Alembic's
op layer cannot express (``PARTITION BY RANGE`` + a composite primary key
including the partition key), so it is created with explicit SQL, along with its
monthly partitions, a ``DEFAULT`` catch-all partition, and its indexes.

The ``audit_log`` table is made append-only at the database level by a trigger
that rejects UPDATE/DELETE — defence in depth for the immutable audit trail.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.db.models import Base

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Monthly partition window for repayment_event. The DEFAULT partition guarantees
# inserts outside this window still succeed; production rolls the window forward
# with a scheduled maintenance job (see docs/DATA_MODEL.md).
_PARTITION_START = dt.date(2023, 1, 1)
_PARTITION_MONTHS = 48

_METADATA = Base.metadata

# Tables introduced *at this revision* (pinned by name, not "whatever is in the
# metadata now"). Pinning keeps this migration immutable: adding a model in a
# later revision must not change what 0001 creates. ``repayment_event`` is the
# partitioned table, created separately with raw DDL.
_REVISION_TABLES: tuple[str, ...] = (
    "operator",
    "user_account",
    "api_credential",
    "customer",
    "consent_record",
    "enrichment_signal",
    "feature_snapshot",
    "score_result",
    "cooperative_lift",
    "audit_log",
    "model_version",
)


def _standard_tables() -> list[sa.Table]:
    """The non-partitioned tables belonging to this revision, from the metadata."""
    return [_METADATA.tables[name] for name in _REVISION_TABLES]


def _add_month(d: dt.date) -> dt.date:
    return dt.date(d.year + (d.month // 12), (d.month % 12) + 1, 1)


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Standard tables + every ENUM type, straight from the model metadata
    #    (single source of truth). create_all creates all metadata-bound ENUM
    #    types — including repayment_status, used by the partitioned table below.
    _METADATA.create_all(bind=bind, tables=_standard_tables(), checkfirst=False)

    # 2. Partitioned parent table.
    op.execute(
        """
        CREATE TABLE repayment_event (
            id                UUID         NOT NULL,
            due_date          DATE         NOT NULL,
            operator_id       UUID         NOT NULL,
            customer_id       UUID         NOT NULL,
            instalment_amount NUMERIC(14, 2) NOT NULL,
            currency          VARCHAR(3)   NOT NULL,
            paid_date         DATE,
            status            repayment_status NOT NULL,
            created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
            CONSTRAINT pk_repayment_event PRIMARY KEY (id, due_date),
            CONSTRAINT fk_repayment_event_operator_id_operator
                FOREIGN KEY (operator_id) REFERENCES operator (id) ON DELETE RESTRICT,
            CONSTRAINT fk_repayment_event_customer_id_customer
                FOREIGN KEY (customer_id) REFERENCES customer (id) ON DELETE CASCADE
        ) PARTITION BY RANGE (due_date)
        """
    )

    # 3. Monthly partitions + DEFAULT catch-all.
    month = _PARTITION_START
    for _ in range(_PARTITION_MONTHS):
        nxt = _add_month(month)
        name = f"repayment_event_{month.year:04d}_{month.month:02d}"
        op.execute(
            f"CREATE TABLE {name} PARTITION OF repayment_event "
            f"FOR VALUES FROM ('{month.isoformat()}') TO ('{nxt.isoformat()}')"
        )
        month = nxt
    op.execute("CREATE TABLE repayment_event_default PARTITION OF repayment_event DEFAULT")

    # 4. Indexes on the partitioned parent (propagate to every partition).
    op.create_index(
        "ix_repayment_event_customer_id_due_date",
        "repayment_event",
        ["customer_id", "due_date"],
    )
    op.create_index("ix_repayment_event_operator_id", "repayment_event", ["operator_id"])
    op.create_index("ix_repayment_event_status", "repayment_event", ["status"])

    # 5. Append-only enforcement for the audit log.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION gridscore_block_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only: % is not permitted', TG_OP;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION gridscore_block_mutation()
        """
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Audit trigger/function first.
    op.execute("DROP TRIGGER IF EXISTS audit_log_immutable ON audit_log")
    op.execute("DROP FUNCTION IF EXISTS gridscore_block_mutation()")

    # The partitioned table (CASCADE drops partitions + indexes) before its FK
    # targets (operator, customer) are removed by drop_all.
    op.execute("DROP TABLE IF EXISTS repayment_event CASCADE")

    # Remaining tables + every ENUM type, from the metadata.
    _METADATA.drop_all(bind=bind, tables=_standard_tables(), checkfirst=True)
