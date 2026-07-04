"""Synthetic data engine.

Generates realistic cooperative PAYG data with *genuine* predictive structure:
default is a real logistic function of the Appendix A features plus irreducible
noise. Everything produced here is clearly labelled synthetic.
"""

from __future__ import annotations

from app.ml.data_gen.config import DEFAULT_COEFFICIENTS, GeneratorConfig, OperatorSpec
from app.ml.data_gen.generator import (
    GeneratedCustomer,
    GeneratedPopulation,
    SyntheticGenerator,
)

__all__ = [
    "DEFAULT_COEFFICIENTS",
    "GeneratedCustomer",
    "GeneratedPopulation",
    "GeneratorConfig",
    "OperatorSpec",
    "SyntheticGenerator",
]
