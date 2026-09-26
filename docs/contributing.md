---
title: Make Your First Simulator Change
description: Find the right module, run a focused check, and update contracts and evidence when changing the Metis simulator.
content-type: tutorial
audience: new developers and contributors
prerequisites:
  - getting-started.md
related:
  - implementation.md
  - contracts.md
  - validation/README.md
---

# Make Your First Simulator Change

The simulator has one source of physical truth: Python computes the run, PostgreSQL stores committed measurements, and the browser displays those measurements. Keeping these responsibilities separate makes a small change easier to test and keeps the viewer consistent with a telemetry consumer.

Complete [the local setup](getting-started.md) first. All commands below run from the repository root unless a command says otherwise.

## Get a Quick Win

Run one focused contract test and locate the model it checks:

```bash
uv run pytest tests/contracts/test_contracts.py -q
rg -n 'class SimulationConfig|class MeasurementFrame' backend/src/metis_sim/domain
```

The first command checks configuration and public data rules. The second shows where the Python source of those rules lives. If `rg` is unavailable, use your editor's project search. The full numerical suite takes longer, so a focused test is the fastest feedback while exploring one concern.

## Choose the Right Place to Edit

| If you need to change... | Start here | Check here |
|---|---|---|
| Orbit, frames, sunlight, battery, or operations | `backend/src/metis_sim/models/` | `tests/physics/` and [physics model](physics-model.md) |
| Configuration fields or public response shapes | `backend/src/metis_sim/domain/` | `tests/contracts/` and [contracts](contracts.md) |
| Run creation, pacing, or measurement mapping | `backend/src/metis_sim/application/` | `tests/integration/` |
| Persistence or cursor replay | `backend/src/metis_sim/adapters/` | `tests/integration/test_persistence.py` |
| HTTP permissions or request behavior | `backend/src/metis_sim/api/` | `tests/integration/test_security.py` and [API guide](api.md) |
| Globe, playback, or panels | `frontend/lib/` | `frontend/test/` and [viewer README](https://github.com/metisorbital/satellite-simulation/blob/main/frontend/README.md) |

For a worked path, suppose a public power reading needs a clearer display label. Inspect its definition in `domain/catalog.py`, follow its mapping in `application/measurement.py`, then inspect the panel in `frontend/lib/`. The physical watts still come from `models/`; changing a label must not change the calculation.

## Keep Generated Contracts in Sync

Python Pydantic models define the supported configuration and public API shapes. After changing one of those models, regenerate the JSON Schemas and Dart types:

```bash
uv run python scripts/generate_contracts.py
git diff -- schemas frontend/lib/api/generated.dart frontend/lib/api/shift_log_generated.dart
```

Review the generated diff and commit it with its Python source change. Do not edit `schemas/*.json`, `frontend/lib/api/generated.dart`, or
`frontend/lib/api/shift_log_generated.dart` directly.
The Shift Log contract is generated separately from public telemetry contracts. Add a contract test for a new accepted field and a meaningful rejected input when validation changes.

## Run Checks for the Changed Boundary

```bash
uv run ruff check backend/src backend/migrations tests scripts examples
uv run ruff format --check backend/src backend/migrations tests scripts examples
uv run mypy backend/src scripts/generate_contracts.py
uv run pytest -q
npm --prefix frontend ci
npm --prefix frontend run prepare:cesium
cd frontend
flutter pub get
flutter analyze
flutter test
flutter build web --no-web-resources-cdn
cd ..
```

Run the relevant focused tests during development, then the full checks before handing off a change. PostgreSQL integration tests need `METIS_TEST_DATABASE_URL` pointing to an isolated test database; without it, a skipped test is not database evidence. The [validation guide](validation/README.md) lists the browser and sustained throughput gates and explains how to reproduce them.

## Record What You Verified

For a change to the model or an API boundary, describe the affected input, expected output, test command, and result. Record numerical tolerance and model limits when physics changes. Keep Python public classes and functions typed and documented with NumPy-style docstrings. Use idiomatic `///` documentation comments for Dart classes and methods. If a new public value is added, check that private scenarios, seeds, thresholds, and future health still cannot appear in viewer or consumer output.

The [specification](specification.md), [physics model](physics-model.md), and [contracts](contracts.md) define the acceptance gates. A passing test supports the part it exercised; it does not by itself establish flight accuracy or satisfy unrelated gates.


## Build API Documentation from Docstrings

The [database reference](reference/database.md) also renders directly from SQLAlchemy
metadata during these builds. Edit `backend/src/metis_sim/adapters/tables.py` and
its migrations when changing storage; the diagram and column reference update automatically.


Install the locked development dependencies with `uv sync --frozen`.
The normal documentation commands generate the Python reference directly from source:

```bash
uv run zensical build --strict
uv run zensical serve
```

Open the **Python API Reference** section in the preview. Zensical's native
[mkdocstrings integration](https://zensical.org/docs/compatibility/mkdocs/plugins/#mkdocstrings)
loads `mkdocstrings-python` with `backend/src` as its source path. The handler parses
[NumPy-style docstrings](https://mkdocstrings.github.io/python/usage/configuration/docstrings/)
and renders signatures, class attributes, methods, source, and internal type links.
No separate API-generation command or copied class description is required.
Python sources inside this repository are watched during preview.

Document public Python classes and functions in their source files. Use a concise
summary and the relevant NumPy sections: `Parameters`, `Attributes`, `Returns`,
`Raises`, `Examples`, and `Notes`. Include units, array shapes, and privacy boundaries
where they affect the caller. Type annotations describe the Python type; prose
explains its meaning and constraints. For example:

```python
def remaining_energy(capacity_wh: float, soc: float) -> float:
    """Calculate stored energy from a fractional state of charge.

    Parameters
    ----------
    capacity_wh : float
        Battery capacity in watt-hours.
    soc : float
        Dimensionless state of charge between zero and one.

    Returns
    -------
    float
        Stored battery energy in watt-hours.
    """
    return capacity_wh * soc
```

The pages in `docs/reference/` contain module directives such as
`::: metis_sim.models.engine`. New public classes and functions in those modules
appear automatically. For a new module, add its directive to the appropriate
reference page; if adding a new page, also add it to `zensical.toml` navigation.
Do not list imported third-party objects or private helpers as project APIs.
The reference excludes underscore-prefixed members and does not expand inherited
third-party methods. Keep the HTTP/OpenAPI and JSON Schema contracts as the external
consumer reference; documenting an internal Python class does not make it an SDK.
