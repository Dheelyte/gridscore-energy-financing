#!/usr/bin/env python
"""In-process latency benchmark for the scoring compute path (no server/DB).

Times the CPU-bound work behind ``POST /v1/score`` — feature extraction,
calibrated inference, and the SHAP explanation — and reports p50/p95/throughput.

    python scripts/bench_scoring.py [iterations]
"""

from __future__ import annotations

import statistics
import sys
import tempfile
import time

from app.domain.enums import ScoreView
from app.ml.data_gen import GeneratorConfig, SyntheticGenerator
from app.ml.dataset import raw_from_generated, reference_date_for
from app.ml.explain import ShapExplainer
from app.ml.features import FeatureExtractor
from app.ml.training import train


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    pop = SyntheticGenerator(GeneratorConfig(n_customers=800, seed=5)).generate()
    model = train(pop, tracking_uri=f"sqlite:///{tempfile.mkdtemp()}/m.db").model

    extractor = FeatureExtractor()
    explainer = ShapExplainer(model)
    ref = reference_date_for(pop)
    raws = [raw_from_generated(c) for c in pop.customers[:n]]

    latencies: list[float] = []
    for raw in raws:
        start = time.perf_counter()
        feats = extractor.extract(raw, ScoreView.POOLED, reference_date=ref)
        model.predict_pd(feats)
        explainer.explain(feats, top_k=5)
        latencies.append((time.perf_counter() - start) * 1000.0)

    latencies.sort()
    p50 = statistics.median(latencies)
    p95 = latencies[int(len(latencies) * 0.95)]
    mean = statistics.mean(latencies)
    print(f"\n=== Scoring compute benchmark (n={len(latencies)}) ===")
    print(f"  p50      {p50:6.2f} ms")
    print(f"  p95      {p95:6.2f} ms")
    print(f"  mean     {mean:6.2f} ms")
    print(f"  throughput ~{1000.0 / mean:6.0f} scores/s/core")


if __name__ == "__main__":
    main()
