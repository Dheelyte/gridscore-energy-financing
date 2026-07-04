#!/usr/bin/env python
"""Export the FastAPI OpenAPI schema to a JSON file (no running server needed).

    python scripts/export_openapi.py [output_path]

The frontend turns this into typed client code via `npm run gen:api`
(openapi-typescript), so the SPA and backend can never silently drift.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "frontend" / "openapi.json"
    app = create_app(Settings(_env_file=None))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    print(f"OpenAPI schema written to {out} ({len(app.openapi()['paths'])} paths)")


if __name__ == "__main__":
    main()
