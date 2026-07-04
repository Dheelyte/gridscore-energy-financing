"""End-to-end API tests: auth, RBAC, tenant isolation, rate-limit headers, and
the cooperative-lift endpoint — against a real Postgres + a trained model."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.core.security import TokenType, create_token, generate_api_key, hash_password
from app.db.models import ApiCredential, UserAccount
from app.db.repositories import CustomerRepository
from app.domain.enums import UserRole, UserStatus
from app.main import create_app
from app.ml.data_gen import GeneratorConfig, SyntheticGenerator
from app.ml.data_gen.generator import GeneratedPopulation
from app.ml.data_gen.persistence import SyntheticDataWriter
from app.ml.model import ScoringModel
from app.ml.training import train

pytestmark = pytest.mark.integration

_PASSWORD = "demo-password-123"


@pytest.fixture(scope="module")
def api_population() -> GeneratedPopulation:
    return SyntheticGenerator(GeneratorConfig(n_customers=600, seed=11)).generate()


@pytest.fixture(scope="module")
def api_model(
    api_population: GeneratedPopulation, tmp_path_factory: pytest.TempPathFactory
) -> ScoringModel:
    uri = f"sqlite:///{tmp_path_factory.mktemp('mlruns') / 'mlflow.db'}"
    return train(api_population, tracking_uri=uri).model


@dataclass
class ApiContext:
    client: AsyncClient
    settings: Settings
    operator_a: UUID
    operator_b: UUID
    demo_customer: UUID
    operator_b_customer: UUID
    admin_user: UUID
    operator_a_user: UUID
    api_key: str

    def bearer(self, user_id: UUID) -> dict[str, str]:
        token = create_token(
            subject=str(user_id),
            token_type=TokenType.ACCESS,
            secret_key=self.settings.secret_key.get_secret_value(),
        )
        return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def api(
    pg_url: str, api_population: GeneratedPopulation, api_model: ScoringModel
) -> AsyncIterator[ApiContext]:
    settings = Settings(_env_file=None, secret_key="api-test-secret", decision_threshold=0.25)
    app = create_app(settings)
    engine = create_async_engine(pg_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    app.state.db_engine = engine
    app.state.db_sessionmaker = factory
    app.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    app.state.scoring_model = api_model
    # Pre-seed the (otherwise slow, retraining) network-effect cache.
    app.state.network_effect = [
        {"operators": 1, "auc": 0.72, "avg_history_months": 3.0, "customers_covered": 100},
        {"operators": 5, "auc": 0.78, "avg_history_months": 12.0, "customers_covered": 600},
    ]

    async with factory() as s:
        await s.execute(text("TRUNCATE operator, audit_log RESTART IDENTITY CASCADE"))
        summary = await SyntheticDataWriter(s).write(api_population)
        op_a, op_b = summary.operator_ids[0], summary.operator_ids[1]
        admin = UserAccount(
            email="admin@gridscore.ai",
            hashed_password=hash_password(_PASSWORD),
            role=UserRole.PLATFORM_ADMIN,
            operator_id=None,
            status=UserStatus.ACTIVE,
        )
        op_a_user = UserAccount(
            email="ops@operator-a.example",
            hashed_password=hash_password(_PASSWORD),
            role=UserRole.OPERATOR_ADMIN,
            operator_id=op_a,
            status=UserStatus.ACTIVE,
        )
        s.add_all([admin, op_a_user])
        await s.flush()
        key = generate_api_key()
        s.add(
            ApiCredential(
                operator_id=op_a,
                key_prefix=key.prefix,
                hashed_secret=key.hashed_secret,
                scopes=["score:read"],
            )
        )
        cust_b = (await CustomerRepository(s).list_for_operator(op_b))[0]
        await s.commit()
        ctx_ids = (op_a, op_b, summary.demo_customer_id, cust_b.id, admin.id, op_a_user.id)

    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield ApiContext(
                client=client,
                settings=settings,
                operator_a=ctx_ids[0],
                operator_b=ctx_ids[1],
                demo_customer=ctx_ids[2],
                operator_b_customer=ctx_ids[3],
                admin_user=ctx_ids[4],
                operator_a_user=ctx_ids[5],
                api_key=key.full_key,
            )
    finally:
        # This suite COMMITS to the shared container DB; clean up so the
        # rollback-isolated suites that follow see an empty database.
        async with factory() as cleanup:
            await cleanup.execute(text("TRUNCATE operator, audit_log RESTART IDENTITY CASCADE"))
            await cleanup.commit()
        await engine.dispose()


# --------------------------------------------------------------------------- #
async def test_login_and_me(api: ApiContext) -> None:
    resp = await api.client.post(
        "/v1/auth/login",
        data={"username": "ops@operator-a.example", "password": _PASSWORD},
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = await api.client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "operator_admin"
    assert body["operator_id"] == str(api.operator_a)


async def test_unauthenticated_requests_use_error_envelope(api: ApiContext) -> None:
    resp = await api.client.get("/v1/customers")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthenticated"


async def test_bad_login_rejected(api: ApiContext) -> None:
    resp = await api.client.post(
        "/v1/auth/login", data={"username": "ops@operator-a.example", "password": "wrong"}
    )
    assert resp.status_code == 401


async def test_tenant_isolation_blocks_cross_operator_reads(api: ApiContext) -> None:
    headers = api.bearer(api.operator_a_user)

    # Operator A sees only its own customers.
    own = await api.client.get("/v1/customers", headers=headers)
    assert own.status_code == 200
    assert all(c["home_operator_id"] == str(api.operator_a) for c in own.json())

    # Operator A cannot read Operator B's customer (404, not 403 — no leak).
    cross = await api.client.get(f"/v1/customers/{api.operator_b_customer}", headers=headers)
    assert cross.status_code == 404


async def test_rbac_operator_cannot_manage_operators(api: ApiContext) -> None:
    resp = await api.client.post(
        "/v1/operators",
        headers=api.bearer(api.operator_a_user),
        json={"name": "Sneaky Co", "country": "KE"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_platform_admin_can_onboard_operator_and_issue_key(api: ApiContext) -> None:
    headers = api.bearer(api.admin_user)
    created = await api.client.post(
        "/v1/operators", headers=headers, json={"name": "New Solar Co", "country": "TZ"}
    )
    assert created.status_code == 201
    operator_id = created.json()["id"]

    key = await api.client.post(f"/v1/operators/{operator_id}/api-keys", headers=headers)
    assert key.status_code == 201
    assert key.json()["api_key"].startswith("gsk_")


async def test_score_via_api_key_sets_rate_limit_headers(api: ApiContext) -> None:
    resp = await api.client.post(
        "/v1/score",
        headers={"X-API-Key": api.api_key},
        json={"customer_id": str(api.demo_customer), "view": "pooled"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert 300 <= body["energy_credit_score"] <= 850
    assert len(body["top_factors"]) == 5
    # Rate-limit headers present and decrementing.
    assert int(resp.headers["X-RateLimit-Remaining"]) < int(resp.headers["X-RateLimit-Limit"])


async def test_cooperative_endpoint_shows_decision_flip(api: ApiContext) -> None:
    resp = await api.client.post(
        "/v1/score/cooperative",
        headers=api.bearer(api.operator_a_user),
        json={"customer_id": str(api.demo_customer)},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["solo"]["approved"] is False
    assert body["pooled"]["approved"] is True
    assert body["decision_flips"] is True
    assert body["pooled"]["energy_credit_score"] > body["solo"]["energy_credit_score"]


async def test_ingest_events_via_api(api: ApiContext) -> None:
    events = [
        {
            "raw_identifier": "+254700999001",
            "instalment_amount": "15.00",
            "currency": "USD",
            "due_date": "2024-04-05",
            "status": "on_time",
        },
        {
            "raw_identifier": "+254700999001",
            "instalment_amount": "15.00",
            "currency": "USD",
            "due_date": "2024-05-05",
            "status": "on_time",
        },
        {"raw_identifier": "", "currency": "USD"},  # invalid -> per-row error
    ]
    resp = await api.client.post(
        "/v1/ingest/events",
        headers={"X-API-Key": api.api_key},
        json={"events": events, "enrich": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["report"]["inserted"] == 2
    assert body["report"]["failed"] == 1
    assert body["customers_enriched"] == 1
    assert body["signals_written"] == 3
    # Rate-limit headers present on the ingestion route too.
    assert "X-RateLimit-Limit" in resp.headers


async def test_portfolio_summary_reflects_scores(api: ApiContext) -> None:
    headers = api.bearer(api.operator_a_user)
    # No scores yet → an empty-but-valid summary.
    empty = await api.client.get("/v1/portfolio/summary", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["scored_customers"] == 0
    assert empty.json()["total_customers"] > 0

    # Score the demo customer, then the portfolio reflects it.
    await api.client.post(
        "/v1/score", headers=headers, json={"customer_id": str(api.demo_customer), "view": "pooled"}
    )
    summary = (await api.client.get("/v1/portfolio/summary", headers=headers)).json()
    assert summary["scored_customers"] == 1
    assert sum(summary["tier_distribution"].values()) == 1


async def test_admin_health_is_platform_admin_only(api: ApiContext) -> None:
    # Operator admin is forbidden.
    forbidden = await api.client.get("/v1/admin/health", headers=api.bearer(api.operator_a_user))
    assert forbidden.status_code == 403

    # Platform admin sees real cooperative counts.
    ok = await api.client.get("/v1/admin/health", headers=api.bearer(api.admin_user))
    assert ok.status_code == 200
    body = ok.json()
    assert body["operators"] >= 2
    assert body["customers"] > 0
    assert body["repayment_events"] > 0


async def test_lender_analytics_rbac_and_aggregates(api: ApiContext) -> None:
    admin = api.bearer(api.admin_user)
    # Operators cannot see lender analytics.
    forbidden = await api.client.get(
        "/v1/analytics/portfolio", headers=api.bearer(api.operator_a_user)
    )
    assert forbidden.status_code == 403

    # An operator scores its customer (admins aren't bound to an operator).
    scored = await api.client.post(
        "/v1/score",
        headers=api.bearer(api.operator_a_user),
        json={"customer_id": str(api.demo_customer), "view": "pooled"},
    )
    assert scored.status_code == 200
    portfolio = (await api.client.get("/v1/analytics/portfolio", headers=admin)).json()
    assert portfolio["scored_customers"] >= 1
    assert len(portfolio["operator_concentration"]) >= 2
    assert sum(b["count"] for b in portfolio["pd_histogram"]) == portfolio["scored_customers"]

    # Network-effect endpoint (served from the pre-seeded cache).
    ne = (await api.client.get("/v1/analytics/network-effect", headers=admin)).json()
    assert ne["points"][-1]["auc"] > ne["points"][0]["auc"]


async def test_audit_search(api: ApiContext) -> None:
    # An operator scores (writes audit entries); the admin searches the log.
    scored = await api.client.post(
        "/v1/score/cooperative",
        headers=api.bearer(api.operator_a_user),
        json={"customer_id": str(api.demo_customer)},
    )
    assert scored.status_code == 200
    rows = (
        await api.client.get("/v1/admin/audit?action=score", headers=api.bearer(api.admin_user))
    ).json()
    assert len(rows) >= 1
    assert all("score" in r["action"] for r in rows)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/v1/operators"),  # platform-admin only
        ("POST", "/v1/operators"),
        ("GET", "/v1/admin/health"),
        ("GET", "/v1/admin/audit"),
        ("GET", "/v1/analytics/portfolio"),  # lender only
        ("GET", "/v1/analytics/network-effect"),
    ],
)
async def test_authz_fuzz_operator_cannot_reach_privileged_routes(
    api: ApiContext, method: str, path: str
) -> None:
    """An operator principal must never reach admin/lender routes (403)."""
    resp = await api.client.request(method, path, headers=api.bearer(api.operator_a_user), json={})
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_cross_tenant_customer_subresources_are_404(api: ApiContext) -> None:
    headers = api.bearer(api.operator_a_user)
    cid = api.operator_b_customer
    for path in (
        f"/v1/customers/{cid}",
        f"/v1/customers/{cid}/consents",
        f"/v1/customers/{cid}/scores",
    ):
        resp = await api.client.get(path, headers=headers)
        assert resp.status_code == 404


async def test_metrics_endpoint_and_score_counter(api: ApiContext) -> None:
    await api.client.post(
        "/v1/score",
        headers=api.bearer(api.operator_a_user),
        json={"customer_id": str(api.demo_customer), "view": "pooled"},
    )
    resp = await api.client.get("/metrics")
    assert resp.status_code == 200
    assert "gridscore_http_requests_total" in resp.text
    assert "gridscore_scores_computed_total" in resp.text
    # The response carries a correlation id.
    assert resp.headers.get("X-Request-ID")


async def test_openapi_schema_served(api: ApiContext) -> None:
    resp = await api.client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/v1/score" in paths
    assert "/v1/score/cooperative" in paths
    assert "/v1/ingest/events" in paths
