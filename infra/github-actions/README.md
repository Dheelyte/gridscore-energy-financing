# CI / CD workflows

GitHub only executes workflows that live in `.github/workflows/`, so the
authoritative pipelines live there:

- [`../../.github/workflows/ci.yml`](../../.github/workflows/ci.yml) — lint,
  type-check, test, and image-build for both stacks on every push / PR.

This directory exists per the repository layout convention and holds
deployment-related Actions config (release, deploy) introduced in Stage 10.
