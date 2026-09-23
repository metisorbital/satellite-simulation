---
title: Run a Local Metis Simulation
description: Install the pinned tools, prepare local credentials and PostgreSQL, and open the reproducible browser demo.
content-type: tutorial
audience: developers and evaluators
---

# Run a Local Metis Simulation

The local flow builds the viewer, prepares a PostgreSQL database, creates ignored local credentials, applies migrations, and serves a single simulator writer on loopback.
It does not require a real spacecraft connection.

## Install the Prerequisites

Install Docker with Compose, Python 3.12.12 with uv 0.10.2, and Node 22.23.0.
The committed lockfiles are the dependency source of truth.

From the repository root, install the Python and frontend dependencies and produce the frontend bundle:

```bash
uv sync --frozen
npm ci --prefix frontend
npm --prefix frontend run build
```

## Start PostgreSQL and Create Local Credentials

Start the pinned PostgreSQL 17.6 database on loopback port 55432:

```bash
docker compose up -d --wait db
```

Create the local runtime credentials once:

```bash
uv run metis-sim init
```

This creates `.local/runtime.env` with mode `0600` when it does not already exist.
The file contains the session-signing secret and three distinct role tokens.
It is ignored by Git; do not commit, print, or reuse these values outside local development.

Apply the versioned schema migration:

```bash
uv run metis-sim migrate
```

PostgreSQL is the application database.
SQLite is limited to isolated tests and is not a substitute for the local application database.

## Start the Browser Demo

Prepare genuine persisted history through tick 18,000 and open a paused run:

```bash
uv run metis-sim demo --at 18000
```

Open `http://127.0.0.1:8000` in the same machine's browser.
The shipped configuration is a deterministic six-hour, three-satellite run at one simulated sample per second.
It includes a private synthetic solar-array derating scenario; it is not a claim about natural aging or a real mission.

For a run that begins in the `created` state, use:

```bash
uv run metis-sim demo --at 0
```

Then use the viewer's Start control.
The CLI binds only to `127.0.0.1`, `localhost`, or `::1` in demo mode because unauthenticated bootstrap can issue only a loopback browser session.
`demo --port 8002` automatically allows that loopback browser origin, including IPv6.
An explicit `METIS_ORIGINS` environment value takes precedence; keep it aligned with the browser's exact origin.

## Run the Containerized Service

Build the immutable-base image locally:

```bash
docker build -t metis-simulation:local .
```

To run the application with the repository's base database definition, compose both files:

```bash
docker compose -f compose.yaml -f compose.app.yaml up --build --wait
```

`compose.app.yaml` waits for PostgreSQL, runs `metis-sim migrate`, then starts exactly one Uvicorn worker.
It loads role secrets from `.local/runtime.env` and binds the app port to localhost.
Set `METIS_APP_PORT=8001` before the command when port 8000 is occupied.
The Compose command starts an authenticated service; an operator still creates and prepares a run before a viewer session can be issued.

Container use supports authenticated API calls with deployment-issued bearer role tokens.
The unauthenticated local bootstrap remains restricted to loopback host and peer checks, so a bridge-network browser must not use `METIS_LOCAL_DEMO=1` as a workaround.
Instead, an authenticated operator provisions a fixed run-scoped viewer session through `POST /v1/operator/runs/{run_id}/viewer-session` with a distinct `Idempotency-Key`.
That endpoint issues the HttpOnly cookie and returns the session-bound CSRF token needed for viewer controls.
Use it only after the run is prepared and from an approved operator workflow that forwards the issued cookie to the authorized browser; never expose the operator bearer token to the browser.

## Check the Running Service

Use liveness and readiness separately:

```bash
curl -fsS http://127.0.0.1:8000/health/live
curl -fsS http://127.0.0.1:8000/health/ready
```

`/health/live` confirms the process is responding.
`/health/ready` also requires the database connection and single-writer ownership to be healthy.

## Run the Focused Checks

The repository checks the API, contracts, physics, and viewer independently:

```bash
uv run ruff check backend/src backend/migrations tests scripts examples
uv run ruff format --check backend/src backend/migrations tests scripts examples
uv run mypy backend/src scripts/generate_contracts.py
uv run pytest -q
uv run python scripts/generate_contracts.py
git diff --exit-code -- schemas frontend/src/api/generated.ts
npm --prefix frontend test
npm --prefix frontend run build
```

Read [Implementation Validation and Review](validation/README.md) for the executed numerical, service, browser, and capacity checks and their limits.
The [implementation map](implementation.md) explains the service boundaries behind these commands.
