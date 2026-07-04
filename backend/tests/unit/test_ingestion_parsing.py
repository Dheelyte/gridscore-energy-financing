"""CSV / JSON batch parsing."""

from __future__ import annotations

import pytest

from app.services.ingestion.parsing import BatchParseError, parse_batch

pytestmark = pytest.mark.unit

_CSV = (
    "raw_identifier,instalment_amount,currency,due_date,status\n"
    "+254700111222,12.50,USD,2024-05-01,on_time\n"
    "+254700333444,9.00,USD,2024-05-01,late\n"
)


def test_parse_csv() -> None:
    rows = parse_batch(_CSV, content_type="text/csv")
    assert len(rows) == 2
    assert rows[0]["raw_identifier"] == "+254700111222"
    assert rows[0]["status"] == "on_time"


def test_parse_json_list() -> None:
    rows = parse_batch('[{"raw_identifier": "x", "amount": 1}]', content_type="application/json")
    assert rows == [{"raw_identifier": "x", "amount": 1}]


def test_parse_json_events_envelope() -> None:
    rows = parse_batch('{"events": [{"a": 1}, {"a": 2}]}')
    assert len(rows) == 2


def test_empty_payload_is_empty_list() -> None:
    assert parse_batch("   ") == []


def test_sniffs_format_without_content_type() -> None:
    assert parse_batch('[{"a":1}]') == [{"a": 1}]
    assert len(parse_batch("a,b\n1,2\n")) == 1


def test_invalid_json_raises() -> None:
    with pytest.raises(BatchParseError):
        parse_batch("{not valid json", content_type="application/json")
