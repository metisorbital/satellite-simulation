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

Install Docker with Compose, Python 3.12.12 with uv 0.10.2, Node 22.23.0, and Flutter 3.47.5 (including Dart).
The committed lockfiles are the dependency source of truth.
Check that the tools are available before installing project dependencies:

```bash
python3 --version
uv --version
node --version
npm --version
flutter --version
docker compose version
```

From the repository root, install the Python and frontend dependencies and produce the frontend bundle:

```bash
uv sync --frozen
npm ci --prefix frontend
(cd frontend && flutter pub get --enforce-lockfile && npm run prepare:cesium && flutter build web --release --no-web-resources-cdn)
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

Start the service with a fresh prepared template:

```bash
uv run metis-sim demo --at 0
```

Open `http://127.0.0.1:8000` in the same machine's browser.
The first visit opens `operator1` automatically.
Use the sidebar operator selector to switch to `operator2` or `operator3`.
Switching operators ends the current run.
The stable IDs and names are defined in `backend/src/metis_sim/data/mock_operators.json`.
Each operator has an independent editable run with `user_id` saved in `private.runs`;
editing and resetting retain that ownership.
Use **Start run** to begin the six-hour, three-satellite simulation.
Interactive templates omit the private synthetic fault scenario.

Reloading restores the current operator and run while the signed cookie is valid.
Use the zero-tick startup above for operator demos: `--at` values above zero prepare
a separate paused run for API evaluation, which occupies the service's one-active-run slot.
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

For a public hosted demonstration, set `METIS_PUBLIC_DEMO=1`, `METIS_LOCAL_DEMO=0`, `METIS_COOKIE_SECURE=1`, `METIS_ORIGINS` to the exact HTTPS site origin, and `METIS_DEMO_CONFIG=configs/public-demo.yaml`.
Set `METIS_INTERACTIVE_PUBLIC_DEMO=1` to enable Flutter demo operator sessions and give each selected operator its own bounded editable mission and simulation controls. The first visit selects `operator1`; the sidebar can switch operators.
Without that flag, the legacy shared public bootstrap remains read-only and interactive demo operator sessions are unavailable.
On Render, set `METIS_SOURCE_ID_PER_COMMIT=1` so each zero-downtime deployment owns a distinct writer source while the previous instance drains. Render provides `RENDER_GIT_COMMIT` at runtime. A restart of the same commit still requires stopping the previous writer before the replacement can become ready.
With `METIS_INTERACTIVE_PUBLIC_DEMO=0`, the application starts one short, shared run, issues read-only browser sessions, and replaces a completed run when a visitor reconnects. In interactive mode, browser sessions are scoped to their own missions and may use the exposed editing and run controls; operator credentials and private evaluation data remain server-side.
The service advances one run at a time. If another visitor's run is active, Start returns a busy error until that run stops or finishes. Editing and Reset require stopping the current run first; each creates a new immutable run with fresh streams.
Set a database quota below the hosted PostgreSQL plan's capacity and keep `METIS_PUBLIC_VIEWER_LIMIT` small on resource-constrained plans. Terminal history is expired on restart and before the next public run.

### Render deployment

The root [`render.yaml`](../render.yaml) describes the existing `satellite-simulation` web service and `satellite-simulation-db` database in Frankfurt. The Docker image builds the Flutter viewer and Python service together; Render checks `/health/ready` before routing traffic. The free PostgreSQL plan expires after 30 days, so move to a durable plan before relying on long-lived mission history.

Connect the repository's `main` branch to this Render service and sync the Blueprint in Render. Set its **Auto-Deploy** mode to **After CI Checks Pass** (`autoDeployTrigger: checksPass`). Every push to `main` then runs the GitHub Actions simulation gates, including a Docker image build; Render deploys the commit only if those checks pass. Verify the deployed commit in Render's Deploys tab and request `/health/ready` after rollout. A commit with a failed check is not deployed.
The Documentation workflow always validates the site. It publishes to GitHub Pages only when Pages is configured and the repository variable `PUBLISH_DOCS` is `1`.

Set `METIS_DATABASE_URL` directly in Render to the PostgreSQL internal connection string with the SQLAlchemy `postgresql+psycopg://` scheme. Keep the existing value when syncing the Blueprint; Render's raw `fromDatabase.connectionString` uses `postgresql://`, which selects an unavailable driver here. Render generates the signing secret and three role tokens only when they do not exist, and preserves existing values. Keep these credentials in Render; never put them in GitHub or the browser. `METIS_ORIGINS` in the Blueprint names the existing `onrender.com` origin; update it to the exact HTTPS origin if the service URL or custom domain changes.

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
git diff --exit-code -- schemas frontend/lib/api/generated.dart
npm --prefix frontend test
(cd frontend && flutter analyze && flutter test)
(cd frontend && flutter pub get --enforce-lockfile && npm run prepare:cesium && flutter build web --release --no-web-resources-cdn)
```

For database integration coverage, create a separate empty test database once and point `pytest` to it. The local Compose default password is shown below; adjust the URL if you set `METIS_POSTGRES_PASSWORD`.

```bash
docker compose exec -T db createdb -U metis metis_docs_test
METIS_TEST_DATABASE_URL=postgresql+psycopg://metis:metis-local@127.0.0.1:55432/metis_docs_test uv run pytest -q
```

The test fixtures may replace their test schema. Never point `METIS_TEST_DATABASE_URL` at the application database or a production database. Without this variable, PostgreSQL-specific tests are skipped and the suite does not establish database behavior.

Read [Implementation Validation and Review](validation/README.md) for the executed numerical, service, browser, and capacity checks and their limits.
The [implementation map](implementation.md) explains the service boundaries behind these commands.

## Troubleshoot Local Setup

| Symptom | Check and fix |
|---|---|
| `metis-sim migrate` cannot connect to PostgreSQL | Run `docker compose up -d --wait db` and check that loopback port `55432` is available. The local CLI uses that port by default. |
| `/health/live` works but `/health/ready` returns `503` | The process is up, but database access, writer ownership, or persistence is unhealthy. Check the service log and database health before starting a new run. |
| The API responds but `/` does not show the viewer | Build `frontend/build/web` with `npm ci --prefix frontend` and `(cd frontend && flutter pub get --enforce-lockfile && npm run prepare:cesium && flutter build web --release --no-web-resources-cdn)`, then restart the local demo. The app mounts the viewer only when that directory exists. |
| The browser session or control request returns `401` or `403` | Open the exact loopback origin used by `metis-sim demo`, then reload to refresh the scoped cookie. A different origin must be in `METIS_ORIGINS`; browser controls also require the session CSRF token. |
| Port `8000` is already in use | Run `uv run metis-sim demo --at 0 --port 8002` and open `http://127.0.0.1:8002`. The demo includes this selected loopback port in its default origin list. |

For API status codes and replay behavior, see the [API consumer guide](api.md). To find the module behind a failure, use the [implementation guide](implementation.md).
