"""High-level seeding orchestration (reusable by the CLI and tests)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.data_gen.config import GeneratorConfig
from app.ml.data_gen.generator import GeneratedPopulation, SyntheticGenerator
from app.ml.data_gen.persistence import SeedSummary, SyntheticDataWriter


async def seed_population(
    session: AsyncSession,
    config: GeneratorConfig | None = None,
    *,
    reset: bool = True,
) -> tuple[GeneratedPopulation, SeedSummary]:
    """Generate and persist a cooperative population. Caller owns the commit."""
    population = SyntheticGenerator(config).generate()
    writer = SyntheticDataWriter(session)
    if reset:
        await writer.reset()
    summary = await writer.write(population)
    return population, summary
