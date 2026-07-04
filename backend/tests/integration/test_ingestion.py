"""Ingestion & enrichment end-to-end against a real Postgres + trained model:
validation, idempotency, the PII-leak guarantee, consent-gated enrichment, and a
batch flowing through to a changed score."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import (
    CustomerRepository,
    EnrichmentSignalRepository,
    FeatureSnapshotRepository,
)
from app.domain.enums import ConsentScope, RepaymentStatus, ScoreView
from app.ml.data_gen import GeneratorConfig, SyntheticGenerator
from app.ml.data_gen.generator import GeneratedPopulation
from app.ml.model import ScoringModel
from app.ml.training import train
from app.services.ingestion.anonymise import hash_identity
from app.services.ingestion.enrichment import EnrichmentService
from app.services.ingestion.pipeline import process_ingestion
from app.services.ingestion.service import IngestionService
from app.services.scoring import ScoringService
from tests.integration.conftest import make_operator

pytestmark = pytest.mark.integration

_SALT = "ingest-test-salt"


@pytest.fixture(scope="module")
def ingest_model(tmp_path_factory: pytest.TempPathFactory) -> ScoringModel:
    pop: GeneratedPopulation = SyntheticGenerator(
        GeneratorConfig(n_customers=600, seed=13)
    ).generate()
    uri = f"sqlite:///{tmp_path_factory.mktemp('mlruns') / 'mlflow.db'}"
    return train(pop, tracking_uri=uri).model


def _rows(raw: str, statuses: list[RepaymentStatus], start_month: int = 1) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for i, status in enumerate(statuses):
        month = start_month + i
        due = dt.date(2024, ((month - 1) % 12) + 1, 5)
        paid = None if status is RepaymentStatus.DEFAULTED else due
        rows.append(
            {
                "raw_identifier": raw,
                "instalment_amount": "12.50",
                "currency": "USD",
                "due_date": due.isoformat(),
                "paid_date": paid.isoformat() if paid else None,
                "status": status.value,
            }
        )
    return rows


async def test_ingest_creates_customer_events_and_enriches(session: AsyncSession) -> None:
    op = await make_operator(session, name="Ingest Co A")
    rows = _rows("+254700111000", [RepaymentStatus.ON_TIME] * 3)

    outcome = await process_ingestion(
        session, operator_id=op.id, rows=rows, identity_salt=_SALT, enrich=True
    )

    assert outcome.report.received == 3
    assert outcome.report.inserted == 3
    assert outcome.report.customers_created == 1
    assert outcome.customers_enriched == 1
    assert outcome.signals_written == 3  # mobile-money + airtime + utility

    customer = await CustomerRepository(session).get_by_identity_hash(
        hash_identity("+254700111000", salt=_SALT)
    )
    assert customer is not None
    signals = await EnrichmentSignalRepository(session).list_for_customer(customer.id)
    assert len(signals) == 3
    snapshot = await FeatureSnapshotRepository(session).latest_for_customer(
        customer.id, ScoreView.POOLED
    )
    assert snapshot is not None  # features were recomputed


async def test_reingestion_is_idempotent(session: AsyncSession) -> None:
    op = await make_operator(session, name="Ingest Co B")
    rows = _rows("+254700222000", [RepaymentStatus.ON_TIME] * 4)

    first = await process_ingestion(
        session, operator_id=op.id, rows=rows, identity_salt=_SALT, enrich=False
    )
    second = await process_ingestion(
        session, operator_id=op.id, rows=rows, identity_salt=_SALT, enrich=False
    )

    assert first.report.inserted == 4
    assert second.report.inserted == 0
    assert second.report.duplicates == 4
    assert second.report.customers_created == 0


async def test_per_row_validation_errors_do_not_abort_batch(session: AsyncSession) -> None:
    op = await make_operator(session, name="Ingest Co C")
    rows = _rows("+254700333000", [RepaymentStatus.ON_TIME] * 2)
    rows.append({"raw_identifier": "+254700333000", "currency": "USD"})  # missing fields
    rows.append(
        {
            "raw_identifier": "",
            "instalment_amount": "1.00",
            "currency": "USD",
            "due_date": "2024-09-05",
            "status": "on_time",
        }
    )  # empty identifier

    outcome = await process_ingestion(
        session, operator_id=op.id, rows=rows, identity_salt=_SALT, enrich=False
    )
    assert outcome.report.inserted == 2
    assert outcome.report.failed == 2
    assert len(outcome.report.errors) == 2


async def test_no_raw_pii_is_persisted(session: AsyncSession) -> None:
    op = await make_operator(session, name="Ingest Co D")
    raw = "+254 700-123-456"
    rows = _rows(raw, [RepaymentStatus.ON_TIME])

    await process_ingestion(
        session, operator_id=op.id, rows=rows, identity_salt=_SALT, enrich=False
    )

    expected = hash_identity(raw, salt=_SALT)
    customer = await CustomerRepository(session).get_by_identity_hash(expected)
    assert customer is not None
    assert customer.identity_hash == expected
    assert raw not in customer.identity_hash

    # The raw digits never appear anywhere in the customer table.
    leaked = await session.scalar(
        sa.text(
            "SELECT count(*) FROM customer "
            "WHERE identity_hash LIKE '%254700123456%' OR identity_hash LIKE '%+254%'"
        )
    )
    assert leaked == 0


async def test_enrichment_is_consent_gated(session: AsyncSession) -> None:
    op = await make_operator(session, name="Ingest Co E")
    # Ingest WITHOUT enrichment consent.
    ingestion = IngestionService(session, identity_salt=_SALT)
    rows = _rows("+254700555000", [RepaymentStatus.ON_TIME] * 2)
    result = await ingestion.ingest_rows(rows, op.id, consent_scopes=(ConsentScope.DATA_SHARING,))
    (customer_id,) = result.affected_customer_ids

    enrichment = EnrichmentService(session)
    res = await enrichment.enrich_customer(customer_id)
    assert res.enriched is False
    assert res.signals_written == 0
    assert (await EnrichmentSignalRepository(session).list_for_customer(customer_id)) == []


async def test_ingest_then_enrich_changes_the_score(
    session: AsyncSession, ingest_model: ScoringModel
) -> None:
    op = await make_operator(session, name="Ingest Co F")
    raw = "+254700666000"
    today = dt.date(2026, 6, 1)

    # Thin, unlucky start: two late instalments, no enrichment.
    await process_ingestion(
        session,
        operator_id=op.id,
        rows=_rows(raw, [RepaymentStatus.LATE, RepaymentStatus.LATE]),
        identity_salt=_SALT,
        enrich=False,
    )
    customer = await CustomerRepository(session).get_by_identity_hash(
        hash_identity(raw, salt=_SALT)
    )
    assert customer is not None

    scorer = ScoringService(session, ingest_model, reference_date=today)
    before = await scorer.score_customer(customer.id, op.id, view=ScoreView.POOLED)

    # A fuller, on-time history arrives and enrichment runs.
    await process_ingestion(
        session,
        operator_id=op.id,
        rows=_rows(raw, [RepaymentStatus.ON_TIME] * 10, start_month=3),
        identity_salt=_SALT,
        enrich=True,
    )
    after = await scorer.score_customer(customer.id, op.id, view=ScoreView.POOLED)

    # More on-time history + enrichment improves the score.
    assert after.energy_credit_score > before.energy_credit_score
    assert after.default_probability < before.default_probability
