"""Validation schemas and result types for ingestion."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import RepaymentStatus


class RawRepaymentRow(BaseModel):
    """One incoming repayment record (before anonymisation).

    ``raw_identifier`` is a national ID or phone number; it is hashed at the
    boundary and **never stored**."""

    raw_identifier: str = Field(min_length=1, max_length=128)
    instalment_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217")
    due_date: dt.date
    paid_date: dt.date | None = None
    status: RepaymentStatus

    @field_validator("currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class RowError(BaseModel):
    index: int  # 0-based position in the submitted batch
    message: str


class IngestionReport(BaseModel):
    received: int = 0
    inserted: int = 0
    duplicates: int = 0
    failed: int = 0
    customers_created: int = 0
    errors: list[RowError] = Field(default_factory=list)
