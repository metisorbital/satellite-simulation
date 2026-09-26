# Metis Satellite Simulation

Metis Satellite Simulation produces deterministic synthetic orbit-to-power telemetry and serves an Earth-orbit viewer for a prepared run.
It is a source for a separate monitoring product, not a health-analysis or command system.
Its public HTTP API lets another service discover streams and replay committed measurements after a disconnect.

**New to the project?** Run the demo below, then follow the [API consumer guide](docs/api.md) to read your first telemetry page. Contributors can use the [first-change guide](docs/contributing.md).

The [Flutter viewer guide](docs/frontend.md) covers the frontend build and browser boundary.
The [Python API reference](docs/python-api.md) renders NumPy-style source docstrings automatically.

The documentation site is published at [metisorbital.github.io/satellite-simulation](https://metisorbital.github.io/satellite-simulation/).

## Run a Local Demo

Use Python 3.12.12, uv 0.10.2, Node 22.23.0, Flutter 3.47.5, and Docker with Compose.

```bash
uv sync --frozen
npm ci --prefix frontend
(cd frontend && flutter pub get --enforce-lockfile && npm run prepare:cesium && flutter build web --release --no-web-resources-cdn)
docker compose up -d --wait db
uv run metis-sim init
uv run metis-sim migrate
uv run metis-sim demo --at 0
```

Open `http://127.0.0.1:8000` and log in as `operator1`, `operator2`, or `operator3` with any nonempty demo password.
Each login creates a separate editable run; use **Start run** to begin.
The mock profiles and stable user IDs live in `backend/src/metis_sim/data/mock_operators.json`.
Passwords are not checked or stored. This is a demo identity picker, not production authentication.
The viewer shows the current operator; **Log out** ends that operator's active run and returns to the login panel.
Run ownership is stored in `private.runs.user_id`, including replacement runs made by editing or resetting.

See [Getting Started](docs/getting-started.md) for prerequisites, Docker use, and the authentication boundary.

## Understand the Key Ideas

- **Configuration** defines the satellites, physical models, operations, and run duration. The simulator validates and freezes it before a run begins.
- **Run and tick** identify one execution and its fixed simulated one-second steps. Requested speed changes wall pacing, not the calculated state.
- **Stream and cursor** identify one satellite's durable public sequence and the reader's place in it. Save the returned cursor after processing a page so the next request can resume.
- **Viewer** presents committed measurements and a separately labelled orbit-only trajectory. It does not calculate power or eclipse in the browser.

```text
backend/src/metis_sim/  Python contracts, physics, runner, storage, and API
frontend/lib/          Flutter and Cesium viewer
configs/               Demo and matched healthy run configurations
schemas/               Generated public JSON Schemas
examples/              Standalone telemetry consumer example
tests/                 Physics, contracts, and service checks
docs/                  Guides, normative design, and validation evidence
```

The [implementation guide](docs/implementation.md) maps the data flow and explains where each responsibility lives.

## Common Tasks

| Task | Start here |
|---|---|
| Read telemetry from another service | [API consumer guide](docs/api.md) and [standalone Python example](examples/consumer.py) |
| Understand API objects and Python classes | [Python class reference](docs/python-api.md) and [generated public schema](schemas/public-api.v1.schema.json) |
| Change a configuration or public channel | [First-change guide](docs/contributing.md) and [contracts](docs/contracts.md) |
| Run focused and full checks | [Getting Started](docs/getting-started.md#run-the-focused-checks) |
| Investigate numerical or capacity claims | [Validation evidence](docs/validation/README.md) |

If the browser cannot connect, check `/health/live` and `/health/ready`, then follow the [setup troubleshooting steps](docs/getting-started.md#troubleshoot-local-setup).

The measured maximum tier is ten spacecraft at **19.89× effective speed** with 20× requested: all 120,010 frames were preserved in the sustained run.
The earlier React viewer's ten-spacecraft native browser measurement reached **60.06 FPS**; it is not a Flutter performance result.
See the [capacity report](docs/validation/throughput.md) for the strict timing miss, latency, hardware and measurement limits.

## Read the Authoritative Design and Evidence

The product scope and acceptance gates are in the [specification](docs/specification.md).
The [physics model](docs/physics-model.md) and [configuration and data contracts](docs/contracts.md) are its normative appendices.
The implementation map is in [Implementation](docs/implementation.md).
The executed checks and module reviews are collected in [Implementation Validation and Review](docs/validation/README.md), with separate numerical, browser, service, and capacity evidence.
The model is a validated synthetic demonstration within its stated approximations, not a flight-validated digital twin.

Research and independent review notes are in [docs/research](docs/research/).
They provide context, while the specification and its appendices govern implementation.
