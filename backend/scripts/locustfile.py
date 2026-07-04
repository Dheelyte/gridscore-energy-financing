"""Load test for the scoring endpoint.

    pip install locust
    locust -f backend/scripts/locustfile.py --host http://localhost:8000

Set GRIDSCORE_API_KEY (a machine key for a seeded operator) and
GRIDSCORE_DEMO_CUSTOMER (a customer id that operator owns) in the environment.
"""

from __future__ import annotations

import os

from locust import HttpUser, between, task

_API_KEY = os.environ.get("GRIDSCORE_API_KEY", "")
_CUSTOMER = os.environ.get("GRIDSCORE_DEMO_CUSTOMER", "")


class ScoringUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(3)
    def score(self) -> None:
        self.client.post(
            "/v1/score",
            headers={"X-API-Key": _API_KEY},
            json={"customer_id": _CUSTOMER, "view": "pooled"},
            name="POST /v1/score",
        )

    @task(1)
    def cooperative(self) -> None:
        self.client.post(
            "/v1/score/cooperative",
            headers={"X-API-Key": _API_KEY},
            json={"customer_id": _CUSTOMER},
            name="POST /v1/score/cooperative",
        )
