"""The synthetic generator: latent features → logistic default → raw data.

Design (honest predictive structure):

1. Each customer gets a latent *reliability* and nine latent features (Appendix A)
   drawn from it with independent per-feature noise — so no single feature is a
   perfect proxy for quality.
2. The **default label** is sampled from a logistic model over the standardised
   features plus Gaussian logit noise. The intercept is calibrated to the target
   base rate; the noise keeps the achievable AUC realistic (not perfect).
3. We then emit **raw** ``repayment_event`` and ``enrichment_signal`` records that
   are noisy observations of those latent features, split across a home operator
   and (for some customers) other operators. Stage 3 recomputes features from
   this raw data; the home-only **solo** view is necessarily degraded versus the
   full **pooled** view — the basis of the cooperative network effect.

The label is *not* encoded in the emitted events (it is the future outcome we
predict), which avoids leakage; ``prior_defaults`` reflects past defaults only.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

import numpy as np
import numpy.typing as npt

from app.domain.enums import ConsentScope, ProviderType, RepaymentStatus
from app.ml.data_gen.config import GeneratorConfig, OperatorSpec
from app.ml.feature_schema import FEATURE_NAMES


@dataclass
class GeneratedEvent:
    operator_ref: int  # index into the population's operator list
    due_date: dt.date
    paid_date: dt.date | None
    instalment_amount: Decimal
    currency: str
    status: RepaymentStatus


@dataclass
class GeneratedSignal:
    provider_type: ProviderType
    payload: dict[str, float]
    captured_at: dt.datetime


@dataclass
class GeneratedConsent:
    scope: ConsentScope
    granted: bool
    granted_at: dt.datetime
    expires_at: dt.datetime | None
    source: str


@dataclass
class GeneratedCustomer:
    identity_hash: str
    home_operator_ref: int
    latent_features: dict[str, float]
    default_label: bool
    default_probability_true: float
    events: list[GeneratedEvent]
    signals: list[GeneratedSignal]
    consents: list[GeneratedConsent]
    is_demo: bool = False
    scenario: str | None = None

    def solo_on_time_rate(self) -> float:
        """Observed on-time rate from the home operator's events only."""
        return _on_time_rate(e for e in self.events if e.operator_ref == self.home_operator_ref)

    def pooled_on_time_rate(self) -> float:
        """Observed on-time rate across the full cooperative history."""
        return _on_time_rate(self.events)


@dataclass
class GeneratedPopulation:
    operators: list[OperatorSpec]
    customers: list[GeneratedCustomer]
    intercept: float
    config: GeneratorConfig = field(repr=False)

    @property
    def default_rate(self) -> float:
        if not self.customers:
            return 0.0
        return sum(c.default_label for c in self.customers) / len(self.customers)

    @property
    def n_events(self) -> int:
        return sum(len(c.events) for c in self.customers)

    def bayes_auc(self) -> float:
        """AUC of the *true* default probability vs the sampled label — the
        Bayes-optimal ceiling. A trained model should land near, but below, this."""
        probs = np.array([c.default_probability_true for c in self.customers])
        labels = np.array([c.default_label for c in self.customers], dtype=bool)
        return _auc(probs, labels)


def _sigmoid(x: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    return 1.0 / (1.0 + np.exp(-x))


def _on_time_rate(events: Iterable[GeneratedEvent]) -> float:
    evs = list(events)
    if not evs:
        return 0.0
    on_time = sum(1 for e in evs if e.status is RepaymentStatus.ON_TIME)
    return on_time / len(evs)


def _auc(scores: npt.NDArray[np.float64], labels: npt.NDArray[np.bool_]) -> float:
    """ROC-AUC via the Mann-Whitney U statistic (rank-based, ties handled)."""
    pos = scores[labels]
    neg = scores[~labels]
    if pos.size == 0 or neg.size == 0:
        return float("nan")
    order = np.argsort(scores)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, scores.size + 1)
    # Average ranks for ties.
    _assign_tie_ranks(scores, ranks)
    rank_sum_pos = ranks[labels].sum()
    auc = (rank_sum_pos - pos.size * (pos.size + 1) / 2) / (pos.size * neg.size)
    return float(auc)


def _assign_tie_ranks(scores: npt.NDArray[np.float64], ranks: npt.NDArray[np.float64]) -> None:
    order = np.argsort(scores, kind="mergesort")
    sorted_scores = scores[order]
    i = 0
    n = scores.size
    while i < n:
        j = i
        while j + 1 < n and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        if j > i:
            avg = (ranks[order[i]] + ranks[order[j]]) / 2.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
        i = j + 1


class SyntheticGenerator:
    """Deterministic (seeded) generator producing a cooperative population."""

    def __init__(self, config: GeneratorConfig | None = None) -> None:
        self.config = config or GeneratorConfig()
        self._rng = np.random.default_rng(self.config.seed)

    # -- public API -------------------------------------------------------- #
    def generate(self) -> GeneratedPopulation:
        cfg = self.config
        n = cfg.n_customers
        latent = self._sample_latent(n)
        probs, labels, intercept = self._calibrate_probabilities(latent)

        customers: list[GeneratedCustomer] = []
        for i in range(n):
            features = {name: float(latent[name][i]) for name in FEATURE_NAMES}
            customers.append(
                self._build_customer(
                    features=features,
                    default_label=bool(labels[i]),
                    default_probability=float(probs[i]),
                )
            )

        customers.append(self._build_borderline_demo_customer())

        return GeneratedPopulation(
            operators=list(cfg.operators),
            customers=customers,
            intercept=intercept,
            config=cfg,
        )

    # -- latent feature sampling ------------------------------------------- #
    def _sample_latent(self, n: int) -> dict[str, npt.NDArray[np.float64]]:
        rng = self._rng
        g = rng.normal(0.0, 1.0, n)  # shared latent reliability

        history = np.clip(np.round(7 + 10 * _sigmoid(g) + rng.normal(0, 4, n)), 3, 36).astype(float)
        tenure = np.clip(history + rng.integers(0, 18, n), history, 60).astype(float)

        return {
            "payg_repayment_rate": np.clip(0.82 + 0.13 * g + rng.normal(0, 0.09, n), 0.2, 1.0),
            "payg_history_months": history,
            "mm_inflow_stability": np.clip(0.62 + 0.17 * g + rng.normal(0, 0.12, n), 0.02, 0.99),
            "mm_avg_monthly_inflow_usd": np.exp(rng.normal(np.log(160) + 0.12 * g, 0.45, n)).clip(
                20, 5000
            ),
            "airtime_topup_regularity": np.clip(
                0.60 + 0.15 * g + rng.normal(0, 0.14, n), 0.02, 0.99
            ),
            "utility_payment_score": np.clip(0.60 + 0.16 * g + rng.normal(0, 0.14, n), 0.02, 0.99),
            "loan_to_income": np.clip(0.28 - 0.07 * g + rng.normal(0, 0.09, n), 0.03, 1.5),
            "prior_defaults": np.minimum(rng.poisson(np.exp(-0.2 - 0.9 * g)), 8).astype(float),
            "tenure_months": tenure,
        }

    def _calibrate_probabilities(
        self, latent: dict[str, npt.NDArray[np.float64]]
    ) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.bool_], float]:
        """Build the feature signal, sample labels with *irreducible* noise, and
        calibrate the intercept to the target base rate.

        The ``noise`` perturbs the **label** but is invisible to the features, so
        it caps the AUC any feature-based model can reach (it is not part of the
        returned ``feature_pd``). Returns ``(feature_pd, labels, intercept)``."""
        cfg = self.config
        contributions = np.zeros(cfg.n_customers)
        for name, coef in cfg.coefficients.items():
            x = latent[name]
            std = x.std()
            z = (x - x.mean()) / std if std > 0 else np.zeros_like(x)
            contributions += coef * z
        contributions *= cfg.signal_scale

        noise = self._rng.normal(0, cfg.logit_noise_sd, cfg.n_customers)

        # Calibrate the intercept on the *label* distribution (signal + noise).
        lo, hi = -12.0, 12.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if _sigmoid(contributions + noise + mid).mean() < cfg.target_default_rate:
                lo = mid
            else:
                hi = mid
        intercept = (lo + hi) / 2

        label_prob = _sigmoid(contributions + noise + intercept)
        labels = self._rng.random(cfg.n_customers) < label_prob
        # The best a feature-using model could predict — no per-customer noise.
        feature_pd = _sigmoid(contributions + intercept)
        return feature_pd, labels, intercept

    # -- raw record emission ----------------------------------------------- #
    def _build_customer(
        self,
        *,
        features: dict[str, float],
        default_label: bool,
        default_probability: float,
    ) -> GeneratedCustomer:
        rng = self._rng
        cfg = self.config
        home = int(rng.integers(0, cfg.n_operators))
        months = int(features["payg_history_months"])
        rate = features["payg_repayment_rate"]
        n_prior_def = min(int(features["prior_defaults"]), months)
        amount = self._instalment_amount(features)
        currency = cfg.operators[home].currency

        cross = rng.random() < cfg.cross_operator_fraction
        events = self._build_events(
            months=months,
            rate=rate,
            n_prior_def=n_prior_def,
            home=home,
            cross=cross,
            amount=amount,
            currency=currency,
        )
        return GeneratedCustomer(
            identity_hash=self._identity_hash(),
            home_operator_ref=home,
            latent_features=features,
            default_label=default_label,
            default_probability_true=default_probability,
            events=events,
            signals=self._build_signals(features),
            consents=self._build_consents(grant_scoring=rng.random() >= cfg.no_consent_fraction),
        )

    def _build_events(
        self,
        *,
        months: int,
        rate: float,
        n_prior_def: int,
        home: int,
        cross: bool,
        amount: Decimal,
        currency: str,
    ) -> list[GeneratedEvent]:
        rng = self._rng
        cfg = self.config
        other_refs = [r for r in range(cfg.n_operators) if r != home]

        # Per-instalment on-time draw — gives the solo subset genuine sampling
        # noise relative to the pooled whole.
        statuses: list[RepaymentStatus] = [
            RepaymentStatus.ON_TIME if rng.random() < rate else RepaymentStatus.LATE
            for _ in range(months)
        ]
        # Mark prior defaults, preferring already-late instalments.
        late_idx = [i for i, s in enumerate(statuses) if s is RepaymentStatus.LATE]
        rng.shuffle(late_idx)
        for i in late_idx[:n_prior_def]:
            statuses[i] = RepaymentStatus.DEFAULTED
        remaining = n_prior_def - len(late_idx[:n_prior_def])
        if remaining > 0:
            on_time_idx = [i for i, s in enumerate(statuses) if s is RepaymentStatus.ON_TIME]
            rng.shuffle(on_time_idx)
            for i in on_time_idx[:remaining]:
                statuses[i] = RepaymentStatus.DEFAULTED

        events: list[GeneratedEvent] = []
        for k in range(months):
            due = self._due_date(months - 1 - k)
            if cross and other_refs and rng.random() < 0.5:
                op_ref = int(rng.choice(other_refs))
            else:
                op_ref = home
            events.append(
                GeneratedEvent(
                    operator_ref=op_ref,
                    due_date=due,
                    paid_date=self._paid_date(due, statuses[k]),
                    instalment_amount=amount,
                    currency=currency,
                    status=statuses[k],
                )
            )
        return events

    def _build_signals(self, features: dict[str, float]) -> list[GeneratedSignal]:
        captured = dt.datetime.combine(self.config.anchor_month, dt.time(12, 0), tzinfo=dt.UTC)
        return [
            GeneratedSignal(
                ProviderType.MOBILE_MONEY,
                {
                    "avg_monthly_inflow_usd": round(features["mm_avg_monthly_inflow_usd"], 2),
                    "inflow_stability": round(features["mm_inflow_stability"], 4),
                },
                captured,
            ),
            GeneratedSignal(
                ProviderType.AIRTIME,
                {"topup_regularity": round(features["airtime_topup_regularity"], 4)},
                captured,
            ),
            GeneratedSignal(
                ProviderType.UTILITY,
                {"payment_score": round(features["utility_payment_score"], 4)},
                captured,
            ),
        ]

    def _build_consents(self, *, grant_scoring: bool) -> list[GeneratedConsent]:
        granted_at = dt.datetime.combine(
            self.config.anchor_month, dt.time(9, 0), tzinfo=dt.UTC
        ) - dt.timedelta(days=120)
        expires = granted_at + dt.timedelta(days=730)
        consents = [
            GeneratedConsent(ConsentScope.DATA_SHARING, True, granted_at, expires, "ussd"),
            GeneratedConsent(ConsentScope.ENRICHMENT, True, granted_at, expires, "ussd"),
        ]
        consents.append(
            GeneratedConsent(ConsentScope.SCORING, grant_scoring, granted_at, expires, "ussd")
        )
        return consents

    # -- the curated demo customer (reject→approve flip) ------------------- #
    def _build_borderline_demo_customer(self) -> GeneratedCustomer:
        """A reliable customer whose *home* operator sees only a tiny, unlucky
        slice (looks risky → reject) while the *pooled* cooperative history shows
        strong repayment (looks safe → approve). The decision flip is realised by
        the scoring service in Stage 4; here we guarantee the structural setup."""
        home = 0
        other = 1
        currency = self.config.operators[home].currency
        # Deliberately *middling* enrichment so the swing factor is the repayment
        # history: the home operator's thin, unlucky slice looks risky on its own,
        # while the full pooled history is clearly reliable. (With stellar
        # enrichment the model would approve under both views and there would be
        # no flip — the cooperative's value is precisely in the history it adds.)
        features = {
            "payg_repayment_rate": 0.93,  # pooled reality
            "payg_history_months": 28.0,
            "mm_inflow_stability": 0.45,
            "mm_avg_monthly_inflow_usd": 110.0,
            "airtime_topup_regularity": 0.45,
            "utility_payment_score": 0.45,
            "loan_to_income": 0.50,
            "prior_defaults": 0.0,
            "tenure_months": 34.0,
        }
        amount = self._instalment_amount(features)

        events: list[GeneratedEvent] = []
        # Home operator: 3 recent instalments, 2 late (solo on-time rate ≈ 0.33,
        # solo history ≈ 3 months → thin-file + unlucky → looks risky).
        for k, status in enumerate(
            [RepaymentStatus.LATE, RepaymentStatus.ON_TIME, RepaymentStatus.LATE]
        ):
            due = self._due_date(2 - k)
            events.append(
                GeneratedEvent(home, due, self._paid_date(due, status), amount, currency, status)
            )
        # Other operators: 25 earlier instalments, all on time (pooled rate ≈ 0.93,
        # pooled history ≈ 28 months → clearly reliable).
        for k in range(25):
            due = self._due_date(3 + k)
            events.append(
                GeneratedEvent(
                    other,
                    due,
                    self._paid_date(due, RepaymentStatus.ON_TIME),
                    amount,
                    self.config.operators[other].currency,
                    RepaymentStatus.ON_TIME,
                )
            )

        return GeneratedCustomer(
            identity_hash=self.demo_identity_hash(),
            home_operator_ref=home,
            latent_features=features,
            default_label=False,  # genuinely reliable
            default_probability_true=0.06,
            events=events,
            signals=self._build_signals(features),
            consents=self._build_consents(grant_scoring=True),
            is_demo=True,
            scenario="borderline_flip",
        )

    # -- helpers ----------------------------------------------------------- #
    @staticmethod
    def demo_identity_hash() -> str:
        """Stable identity for the demo customer so the UI can always find them."""
        return hashlib.sha256(b"gridscore-demo-borderline-0001").hexdigest()

    def _identity_hash(self) -> str:
        # Synthetic customers have no PII; a random opaque 64-hex digest mirrors
        # the shape of a real salted identity hash.
        return hashlib.sha256(self._rng.bytes(32)).hexdigest()

    def _instalment_amount(self, features: dict[str, float]) -> Decimal:
        usd = max(1.0, features["loan_to_income"] * features["mm_avg_monthly_inflow_usd"])
        return Decimal(f"{usd:.2f}")

    def _due_date(self, months_ago: int) -> dt.date:
        anchor = self.config.anchor_month
        total = (anchor.year * 12 + (anchor.month - 1)) - months_ago
        year, month = divmod(total, 12)
        # Clamp into the partition window's lower bound.
        candidate = dt.date(year, month + 1, 5)
        return max(candidate, dt.date(2023, 1, 5))

    @staticmethod
    def _paid_date(due: dt.date, status: RepaymentStatus) -> dt.date | None:
        if status is RepaymentStatus.ON_TIME:
            return due
        if status is RepaymentStatus.LATE:
            return due + dt.timedelta(days=18)
        return None  # defaulted / pending
