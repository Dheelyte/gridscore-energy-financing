"""Adapt a generated population into a training matrix via the feature pipeline.

Crucially, training features are computed from the **raw** generated events and
signals through the very same :class:`FeatureExtractor` used at inference — so
there is no train/serve skew."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from app.domain.enums import ProviderType, ScoreView
from app.ml.data_gen.generator import GeneratedCustomer, GeneratedPopulation
from app.ml.feature_schema import FEATURE_NAMES
from app.ml.features import EventRecord, FeatureExtractor, RawCustomerData


def reference_date_for(population: GeneratedPopulation) -> dt.date:
    """The notional 'scoring now' date: the month after the latest due month."""
    anchor = population.config.anchor_month
    total = anchor.year * 12 + anchor.month  # +1 month, 1-indexed
    return dt.date(total // 12, (total % 12) + 1, 1)


def raw_from_generated(customer: GeneratedCustomer) -> RawCustomerData:
    """Build view-agnostic raw data from a generated customer."""
    events = [
        EventRecord(
            operator_key=str(e.operator_ref),
            due_date=e.due_date,
            paid_date=e.paid_date,
            status=e.status,
            instalment_amount=e.instalment_amount,
        )
        for e in customer.events
    ]
    signals: dict[ProviderType, dict[str, float]] = {
        s.provider_type: dict(s.payload) for s in customer.signals
    }
    return RawCustomerData(
        home_operator_key=str(customer.home_operator_ref),
        events=events,
        signals=signals,
    )


@dataclass
class Dataset:
    X: npt.NDArray[np.float64]
    y: npt.NDArray[np.int64]
    feature_names: tuple[str, ...]


def build_dataset(
    population: GeneratedPopulation, *, view: ScoreView = ScoreView.POOLED
) -> Dataset:
    """Feature matrix + labels. Training uses the pooled view (full history)."""
    extractor = FeatureExtractor()
    ref = reference_date_for(population)
    rows: list[list[float]] = []
    labels: list[int] = []
    for c in population.customers:
        feats = extractor.extract(raw_from_generated(c), view, reference_date=ref)
        rows.append([feats[name] for name in FEATURE_NAMES])
        labels.append(int(c.default_label))
    return Dataset(
        X=np.array(rows, dtype=np.float64),
        y=np.array(labels, dtype=np.int64),
        feature_names=FEATURE_NAMES,
    )
