"""Parse an uploaded batch (CSV or JSON) into a list of raw row dicts."""

from __future__ import annotations

import csv
import io
import json
from typing import Any


class BatchParseError(ValueError):
    """The uploaded payload could not be parsed at all."""


def parse_batch(content: bytes | str, *, content_type: str | None = None) -> list[dict[str, Any]]:
    """Return a list of raw row dicts from CSV or JSON content.

    JSON may be a top-level list, or an object with an ``events`` array. The
    format is chosen from ``content_type`` when given, else sniffed."""
    text = content.decode("utf-8") if isinstance(content, bytes) else content
    text = text.strip()
    if not text:
        return []

    fmt = _format(content_type, text)
    if fmt == "json":
        return _parse_json(text)
    return _parse_csv(text)


def _format(content_type: str | None, text: str) -> str:
    if content_type:
        if "json" in content_type:
            return "json"
        if "csv" in content_type:
            return "csv"
    return "json" if text[0] in "[{" else "csv"


def _parse_json(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise BatchParseError(f"Invalid JSON: {exc}") from exc
    if isinstance(data, dict):
        data = data.get("events", data.get("rows", []))
    if not isinstance(data, list):
        raise BatchParseError("JSON must be a list of rows or {'events': [...]}.")
    return [dict(row) for row in data]


def _parse_csv(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise BatchParseError("CSV has no header row.")
    return [{k: (v if v != "" else None) for k, v in row.items()} for row in reader]
