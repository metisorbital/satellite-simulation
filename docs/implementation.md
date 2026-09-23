---
title: Understand the Implemented Simulator
description: Map the simulator's configuration, physics, persistence, API, viewer, and deployment boundaries to the authoritative design.
content-type: concept
audience: engineering
---

# Understand the Implemented Simulator

The implementation follows the causal path defined in the [specification](specification.md): validated configuration, deterministic orbit and environment, electrical-power state, durable public telemetry, and a browser viewer.
The viewer consumes backend outputs and does not calculate orbital physics.

## Follow the Service Boundary

`backend/src/metis_sim/domain` contains immutable configuration, public contracts, channel catalogues, and physics-facing types.
`backend/src/metis_sim/models` implements fixed-step J2 propagation, frames, illumination, eclipse, power allocation, and the configured scenario.
`backend/src/metis_sim/application` composes prepared engines, durable commands, and the single writer runner.
`backend/src/metis_sim/adapters` owns configuration parsing, PostgreSQL persistence, cursor reads, and writer ownership.
`backend/src/metis_sim/api` composes FastAPI routes, role authentication, scoped viewer sessions, WebSocket presentation, and static frontend serving.

The contract source is Python Pydantic models.
`scripts/generate_contracts.py` generates JSON Schema and the frontend TypeScript API types from those models.
Do not hand-edit generated files.

## Preserve Simulation and Persistence Semantics

Each run has an immutable resolved configuration, manifest, seed, and per-satellite public stream identity.
The runner is the only writer for a configured source identity and uses a PostgreSQL advisory lock.
It advances at fixed simulated one-second steps, commits frames and events durably, and pauses or fails on persistence pressure rather than silently dropping frames.

The public API exposes allowlisted telemetry, ordinary observed events, current snapshot data, and bounded orbit-only trajectories.
Private scenario details and evaluation truth use separate storage and require the evaluator role.
The exact envelope, cursor, idempotency, and privacy rules are in [Configuration and Data Contracts](contracts.md).

## Use the Viewer Safely

The compiled React/Cesium application is served from `frontend/dist` by the FastAPI process.
Browser controls use a restricted run-scoped session, CSRF token, and explicit origin allowlist.
Local `metis-sim demo` is intentionally loopback-only.

For a bridge-network container or other deployment, an authenticated operator must provision the viewer cookie through `POST /v1/operator/runs/{run_id}/viewer-session` after preparing the run.
A trusted operator-facing workflow forwards that cookie to the authorized browser.
The browser receives no operator bearer credential; it receives only the scoped HttpOnly session and its control CSRF token.
The deployment must allow the browser's exact origin and should set secure cookies when it is served over HTTPS.

The development Vite server proxies API and health requests to the local service.
The production container instead serves the precompiled frontend and API together.

## Build and Operate One Process

The [Dockerfile](../Dockerfile) uses pinned Python 3.12.12 and Node 22.23.0 image digests, installs uv 0.10.2, resolves the frozen Python lockfile, compiles the frontend, and runs as a non-root user.
The [application Compose overlay](../compose.app.yaml) joins the base PostgreSQL service from [compose.yaml](../compose.yaml), migrates before serving, reads ignored local secrets, exposes only localhost, and runs one Uvicorn worker.

Do not add multiprocess workers for this service.
Writer ownership is intentionally one process per source identity.

## Check the Evidence and Model Limits

[Physics Validation Evidence](validation/physics.md) records executed numerical checks for the idealized J2, Astropy Sun/eclipse, and bounded energy-store model.
Those checks support the synthetic model within the stated short-arc envelope.
They do not establish flight ephemeris accuracy, battery electrochemistry, solar-weather behavior, or a mission-grade operational simulator.

[Implementation Validation and Review](validation/README.md) links the separate contract, persistence, security, observability, numerical, browser, and capacity evidence.
The [browser report](validation/browser.md) records actual Cesium scene rendering, clock agreement, reconnect/staleness behavior, and local asset checks.
The specification remains the acceptance source; each report names its workload, measurement method, and limits.
