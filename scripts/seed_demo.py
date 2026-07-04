#!/usr/bin/env python
"""Local convenience wrapper around ``app.cli.seed`` (the real implementation).

    python scripts/seed_demo.py                 # default 2000 customers, reset first
    python scripts/seed_demo.py --customers 500 --seed 7
    python scripts/seed_demo.py --no-reset      # append instead of truncating

In a deployed container the same seeding runs as ``python -m app.cli.seed``.
Run from the repo root or `backend/`; this shim puts `backend/` on the path.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow running from the repo root: add backend/ to the path so `app` imports.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.cli.seed import main  # noqa: E402

if __name__ == "__main__":
    asyncio.run(main())
