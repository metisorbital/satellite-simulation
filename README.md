# Metis Satellite Simulation

Metis Satellite Simulation produces deterministic synthetic orbit-to-power telemetry and serves an Earth-orbit viewer for a prepared run.
It is a source for a separate monitoring product, not a health-analysis or command system.

## Run a Local Demo

Use Python 3.12.12, uv 0.10.2, Node 22.23.0, and Docker with Compose.

```bash
uv sync --frozen
npm ci --prefix frontend
npm --prefix frontend run build
docker compose up -d --wait db
uv run metis-sim init
uv run metis-sim migrate
uv run metis-sim demo --at 18000
```

Open `http://127.0.0.1:8000` after the demo has prepared its paused history.
Use `demo --at 0` for a newly created run and start it with the viewer control.
The six-hour default contains three satellites and one synthetic solar-array derating scenario.

See [Getting Started](docs/getting-started.md) for prerequisites, Docker use, and the authentication boundary.

The measured maximum tier is ten spacecraft at **19.89× effective speed** with 20× requested: all 120,010 frames were preserved in the sustained run.
The separate ten-spacecraft native browser measurement reached **60.06 FPS**.
See the [capacity report](docs/validation/throughput.md) for the strict timing miss, latency, hardware and measurement limits.

## Read the Authoritative Design and Evidence

The product scope and acceptance gates are in the [specification](docs/specification.md).
The [physics model](docs/physics-model.md) and [configuration and data contracts](docs/contracts.md) are its normative appendices.
The implementation map is in [Implementation](docs/implementation.md).
The executed checks and module reviews are collected in [Implementation Validation and Review](docs/validation/README.md), with separate numerical, browser, service, and capacity evidence.
The model is a validated synthetic demonstration within its stated approximations, not a flight-validated digital twin.

Research and independent review notes are in [docs/research](docs/research/).
They provide context, while the specification and its appendices govern implementation.
