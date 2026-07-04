#!/usr/bin/env python
"""Seed the database with a repeatable synthetic demo scenario.

    python scripts/seed_demo.py                 # default 2000 customers, reset first
    python scripts/seed_demo.py --customers 500 --seed 7
    python scripts/seed_demo.py --no-reset      # append instead of truncating

All data produced is **synthetic** and clearly labelled as such in the database
(`synthetic_customer_profile`). The scenario always includes the curated
borderline customer whose home-operator (solo) view looks risky while the pooled
cooperative view looks safe — the reject→approve decision flip realised in
Stage 4.

Run from the `backend/` directory (or with it on PYTHONPATH) so `app` imports.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Allow running from the repo root: add backend/ to the path.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.models.tenancy import UserAccount  # noqa: E402
from app.db.session import create_engine, create_session_factory  # noqa: E402
from app.domain.enums import UserRole, UserStatus  # noqa: E402
from app.ml.data_gen.config import GeneratorConfig  # noqa: E402
from app.ml.data_gen.persistence import SeedSummary  # noqa: E402
from app.ml.data_gen.seed import seed_population  # noqa: E402

# Well-known demo login accounts (SYNTHETIC — for local demos only, never prod).
DEMO_PASSWORD = "GridScore!Demo1"
_DEMO_ACCOUNTS = [
    ("admin@gridscore.ai", UserRole.PLATFORM_ADMIN),
    ("analyst@gridscore.ai", UserRole.OPERATOR_ANALYST),
    ("lender@gridscore.ai", UserRole.LENDER_VIEWER),
]


async def seed_demo_accounts(session: AsyncSession, summary: SeedSummary) -> None:
    """Create the well-known demo login accounts so the app is usable out of the
    box (there is otherwise no platform_admin to bootstrap from). Idempotent: any
    existing accounts with these emails are replaced. The operator analyst belongs
    to the demo customer's **home** operator (ref 0) so they can score them."""
    emails = [email for email, _ in _DEMO_ACCOUNTS]
    await session.execute(delete(UserAccount).where(UserAccount.email.in_(emails)))
    home_operator_id = summary.operator_ids[0]
    for email, role in _DEMO_ACCOUNTS:
        session.add(
            UserAccount(
                email=email,
                hashed_password=hash_password(DEMO_PASSWORD),
                role=role,
                status=UserStatus.ACTIVE,
                operator_id=(
                    home_operator_id if role is UserRole.OPERATOR_ANALYST else None
                ),
            )
        )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed GridScore with synthetic demo data.")
    p.add_argument("--customers", type=int, default=2000, help="number of customers")
    p.add_argument("--seed", type=int, default=GeneratorConfig().seed, help="RNG seed")
    p.add_argument(
        "--no-reset",
        dest="reset",
        action="store_false",
        help="append instead of truncating existing data",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    config = GeneratorConfig(n_customers=args.customers, seed=args.seed)

    engine = create_engine(get_settings())
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            population, summary = await seed_population(
                session, config, reset=args.reset
            )
            await seed_demo_accounts(session, summary)
            await session.commit()
    finally:
        await engine.dispose()

    demo = next(c for c in population.customers if c.is_demo)
    print("\n=== GridScore synthetic seed complete (SYNTHETIC DATA) ===")
    print(f"  operators ............. {summary.operators}")
    print(f"  customers ............. {summary.customers}")
    print(f"  repayment events ...... {summary.repayment_events}")
    print(f"  enrichment signals .... {summary.enrichment_signals}")
    print(f"  consent records ....... {summary.consent_records}")
    print(f"  base default rate ..... {summary.default_rate:.1%}  (target 10-20%)")
    print(f"  feature-AUC ceiling ... {population.bayes_auc():.3f}")
    print("\n  Borderline demo customer (reject→approve flip):")
    print(f"    identity_hash ....... {summary.demo_identity_hash}")
    print(f"    customer_id ......... {summary.demo_customer_id}")
    print(
        f"    solo on-time rate ... {demo.solo_on_time_rate():.0%}  (home operator only)"
    )
    print(
        f"    pooled on-time rate . {demo.pooled_on_time_rate():.0%}  (full cooperative)"
    )
    print("\n  Demo login accounts (password for all: " f"{DEMO_PASSWORD!r}):")
    for email, role in _DEMO_ACCOUNTS:
        print(f"    {role.value:<16} {email}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
