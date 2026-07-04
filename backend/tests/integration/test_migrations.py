"""Acceptance: the migration applies to an empty DB and rolls back cleanly."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine

import app.core.config as config_module

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.mark.integration
def test_migration_upgrade_then_downgrade_roundtrip() -> None:
    """On a *fresh* database: upgrade head, verify the schema, downgrade base,
    and verify nothing of ours remains."""
    from testcontainers.postgres import PostgresContainer

    previous = os.environ.get("GRIDSCORE_DATABASE_URL")
    with PostgresContainer("postgres:16-alpine") as pg:
        host = pg.get_container_host_ip()
        port = pg.get_exposed_port(5432)
        async_url = f"postgresql+asyncpg://{pg.username}:{pg.password}@{host}:{port}/{pg.dbname}"
        sync_url = f"postgresql+psycopg2://{pg.username}:{pg.password}@{host}:{port}/{pg.dbname}"

        os.environ["GRIDSCORE_DATABASE_URL"] = async_url
        config_module.get_settings.cache_clear()
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))

        engine = create_engine(sync_url)
        try:
            command.upgrade(cfg, "head")
            with engine.connect() as conn:
                tables = conn.scalar(
                    sa.text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_type='BASE TABLE'"
                    )
                )
                partitions = conn.scalar(
                    sa.text(
                        "SELECT count(*) FROM pg_inherits i "
                        "JOIN pg_class p ON i.inhparent = p.oid "
                        "WHERE p.relname = 'repayment_event'"
                    )
                )
                enums = conn.scalar(sa.text("SELECT count(*) FROM pg_type WHERE typtype = 'e'"))
                trigger = conn.scalar(
                    sa.text(
                        "SELECT count(*) FROM pg_trigger " "WHERE tgname = 'audit_log_immutable'"
                    )
                )

            # 11 standard tables + repayment_event parent + 49 partitions
            # + synthetic_customer_profile (0002) + alembic_version = 63.
            assert tables == 63
            assert partitions == 49  # 48 monthly + 1 DEFAULT
            assert enums == 9
            assert trigger == 1

            command.downgrade(cfg, "base")
            with engine.connect() as conn:
                remaining = conn.scalar(
                    sa.text(
                        "SELECT count(*) FROM information_schema.tables "
                        "WHERE table_schema='public' AND table_type='BASE TABLE' "
                        "AND table_name <> 'alembic_version'"
                    )
                )
                remaining_enums = conn.scalar(
                    sa.text("SELECT count(*) FROM pg_type WHERE typtype = 'e'")
                )
            assert remaining == 0
            assert remaining_enums == 0
        finally:
            engine.dispose()
            if previous is None:
                os.environ.pop("GRIDSCORE_DATABASE_URL", None)
            else:
                os.environ["GRIDSCORE_DATABASE_URL"] = previous
            config_module.get_settings.cache_clear()
