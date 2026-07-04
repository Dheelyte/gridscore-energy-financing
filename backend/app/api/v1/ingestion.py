"""Ingestion endpoints: streaming events (inline) and batch file uploads (async)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.errors import APIError, AuthorizationError
from app.api.v1.deps import Principal, get_session, get_settings_dep, rate_limit, require_roles
from app.core.config import Settings
from app.domain.enums import UserRole
from app.services.ingestion.parsing import BatchParseError, parse_batch
from app.services.ingestion.pipeline import process_ingestion
from app.services.ingestion.schemas import IngestionReport

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_operator_roles = require_roles(UserRole.OPERATOR_ADMIN, UserRole.OPERATOR_ANALYST)
_INGEST_RATE_LIMIT = Depends(rate_limit(limit=30, window_seconds=60))


class IngestEventsRequest(BaseModel):
    events: list[dict[str, Any]] = Field(description="Raw repayment rows to ingest")
    enrich: bool = True


class IngestResponse(BaseModel):
    report: IngestionReport
    customers_enriched: int
    signals_written: int


class BatchAccepted(BaseModel):
    job_id: str
    status: str
    received: int


class JobStatus(BaseModel):
    job_id: str
    status: str
    result: dict[str, Any] | None = None


def _operator_id(principal: Principal) -> UUID:
    if principal.operator_id is None:
        raise AuthorizationError("This principal is not bound to an operator.")
    return principal.operator_id


@router.post(
    "/events",
    response_model=IngestResponse,
    summary="Ingest repayment events inline (validated, anonymised, idempotent)",
    dependencies=[_INGEST_RATE_LIMIT],
)
async def ingest_events(
    body: IngestEventsRequest,
    principal: Principal = Depends(_operator_roles),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> IngestResponse:
    outcome = await process_ingestion(
        session,
        operator_id=_operator_id(principal),
        rows=body.events,
        identity_salt=settings.identity_hash_salt.get_secret_value(),
        enrich=body.enrich,
    )
    return IngestResponse(
        report=outcome.report,
        customers_enriched=outcome.customers_enriched,
        signals_written=outcome.signals_written,
    )


@router.post(
    "/batch",
    summary="Upload a CSV/JSON batch (processed by the background worker)",
    dependencies=[_INGEST_RATE_LIMIT],
)
async def ingest_batch_upload(
    request: Request,
    file: UploadFile = File(...),
    principal: Principal = Depends(_operator_roles),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> IngestResponse | BatchAccepted:
    raw = await file.read()
    try:
        rows = parse_batch(raw, content_type=file.content_type)
    except BatchParseError as exc:
        raise APIError(str(exc), details={"code": "parse_error"}) from exc

    operator_id = _operator_id(principal)
    payload = {"operator_id": str(operator_id), "rows": rows, "enrich": True}

    pool = getattr(request.app.state, "arq_pool", None)
    if pool is not None:
        from app.workers.queue import enqueue_ingest

        job_id = await enqueue_ingest(pool, payload)
        return BatchAccepted(job_id=job_id, status="queued", received=len(rows))

    # No worker wired (e.g. local/dev): process inline so the upload still works.
    outcome = await process_ingestion(
        session,
        operator_id=operator_id,
        rows=rows,
        identity_salt=settings.identity_hash_salt.get_secret_value(),
        enrich=True,
    )
    return IngestResponse(
        report=outcome.report,
        customers_enriched=outcome.customers_enriched,
        signals_written=outcome.signals_written,
    )


@router.get("/jobs/{job_id}", response_model=JobStatus, summary="Batch job status")
async def job_status(
    job_id: str,
    request: Request,
    _: Principal = Depends(_operator_roles),
) -> JobStatus:
    pool = getattr(request.app.state, "arq_pool", None)
    if pool is None:
        raise APIError("Background worker is not configured.", details={"code": "no_worker"})
    from arq.jobs import Job

    job = Job(job_id, pool)
    status = await job.status()
    result: dict[str, Any] | None = None
    try:
        info = await job.result_info()
        if info is not None and isinstance(info.result, dict):
            result = info.result
    except Exception:
        result = None
    return JobStatus(job_id=job_id, status=str(status), result=result)
