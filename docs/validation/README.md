---
title: Implementation Validation and Review
description: Connect the delivered simulator to its executed numerical, service, browser, and capacity evidence.
content-type: reference
audience: engineering and satellite operations
status: complete with measured maximum performance tier
date: 2026-09-23
---

# Implementation Validation and Review

The delivered application is a Python orbit-to-power simulator with a CesiumJS mission viewer.
Its public telemetry comes from the same committed state that drives the globe and selected spacecraft readings.
The authoritative acceptance requirements remain the [specification](../specification.md), [physics model](../physics-model.md), and [contracts](../contracts.md).

## Evidence by Boundary

The optional September 26 `spacecraft.v1` extension has a separate [telemetry validation record](spacecraft-telemetry.md), including its numerical, database/export, and remaining browser gates. The results below describe the original orbit-to-power delivery.

| Boundary | Executable evidence | Scope |
|---|---|---|
| Configuration and public contracts | `tests/contracts/`, generated JSON schemas, generated TypeScript | Strict JSON/YAML parsing, immutable validated inputs, stable normalization, supported orbits, private-field rejection, producer-neutral observed fixtures. |
| Orbit, frames, eclipse and EPS | [Numerical report](physics.md), [machine-readable results](physics-summary.json), `tests/physics/` | Analytic two-body reference, independent J2 integration, published SOFA matrix, rotating velocity, finite-disk eclipse, energy balance, causal outcomes. |
| Durable lifecycle and replay | `tests/integration/test_service.py`, `test_persistence.py`, `test_determinism.py` | Atomic batches, identity collision rollback, idempotency, committed snapshots, cursor replay, orphan recovery, private terminal censoring, paced 1×/5×/20× equivalence. |
| HTTP/session trust boundaries | `tests/integration/test_security.py` | Roles, run scoping, CSRF/origin checks, forged/expired cookies, HTTPS cookie flags, input limits, slow-socket expiry and redacted errors. |
| Operability and redaction | `tests/integration/test_observability.py` | Request-ID correlation, allowlisted timing and SQLSTATE diagnostics, bounded backpressure logging, safe persisted failure codes and private sentinel exclusion. |
| Actual Cesium interpolation | `frontend/tests/orbit-reference.test.ts`, `tests/fixtures/orbit-interpolation.json` | The production sampled-position factory reproduces stored endpoints and 54 subsecond positions from independent dense DOP853 integration. Maximum measured intermediate error: `6.52669257278191e-7 m`, below the 100 m gate. These are numerical fixture errors, not real-spacecraft accuracy. |
| Browser and offline assets | [Browser report](browser.md), `frontend/tests/browser/`, `frontend/scripts/measure-viewer.mjs` | Compiled UI, real backend connection, clock/measurement agreement, controls, local assets, reconnect/stale semantics, render cadence and WebGL fallback. |
| Sustained capacity | [Capacity report](throughput.md), [machine-readable run](throughput.json), [operational samples](throughput-operations.json) | Ten spacecraft, 12,000 simulated seconds, all 120,010 frames with zero gaps; measured 19.89× effective speed. Strict 20× timing gate missed; the reduced measured tier is advertised under NFR-01. |
| Demo capacity | [Three-spacecraft result](throughput-demo.json) | All gates passed: 1,200 simulated seconds in 60.060870 wall seconds, 3,603 complete frames, read/control p95 17.78/37.36 ms. |
| Packaging | `Dockerfile`, `compose.yaml`, `compose.app.yaml`, `.github/workflows/ci.yml` | Pinned dependencies and base images, non-root image, explicit migration, one worker, local database, reproducible checks. |

The PostgreSQL integration tests require `METIS_TEST_DATABASE_URL`; a skipped PostgreSQL test is not database validation.
Browser fixture tests and the live browser rehearsal are distinct evidence.
CI is configured but has not been run on a remote GitHub runner as part of this local task.

Final local Python checks passed: **80 numerical tests in 112.45 seconds** and **92 contract/service tests in 31.67 seconds**, with the PostgreSQL-specific cases enabled.
The latter includes the persistence, security, pacing, acceptance-edge, batch-I/O and observability regressions.
Ruff lint and formatting pass for all 64 Python files, mypy passes for the 40 application/generator files, and all five generated schema/TypeScript artifacts reproduce without drift.
Expected warnings are the deliberately unsupported future-epoch fixtures and dependency deprecations in Starlette's test adapter; no tests failed or PostgreSQL cases skipped in the final service gate.

The final compiled-browser suite passed **4 tests in 40.1 seconds**.
The rebuilt container runs as UID `10001`; liveness, readiness and the compiled frontend each returned HTTP 200 over a real loopback connection.
A three-spacecraft, four-second run inside that container reached `completed` with all **15 expected frames**, and its private manifest's dependency-lock hash matched the repository lockfile.
The image was built locally as `metis-simulation:local`, digest `sha256:09cb9ec4077dedc54753ff063b1e9d5c33700642efc7f89829358e624cc96f18`.

The final local demo was prepared from the delivered source at tick **18,000**, with **54,003 persisted frames**, and left paused at `2026-09-21T05:00:00Z`.
Native-browser readback confirmed three positioned spacecraft, exact selected-measurement/scene time agreement, zero page errors and no external HTTP requests.
The inspected handoff screenshot is `frontend/artifacts/demo-ready.png` (a local generated artifact).
Select **METIS-02**, keep **20×**, and press **Resume** to watch the developing generation deficit and battery discharge.

## Team and Review Discipline

[AGENTS.md](https://github.com/metisorbital/satellite-simulation/blob/main/AGENTS.md) records the team agreement: explicit ownership, preserved concurrent changes, NumPy-style Python docstrings, narrow interfaces, numerical invariants, independent review, and evidence-based handoff.
The integration lead handled product scope, API/storage composition, acceptance and final integration.
Independent engineers implemented physics, contracts and the viewer; bounded packaging and benchmark work used a smaller-model developer.

Reviews proceeded by concern and module rather than as one whole-repository pass:

| Review | Findings and changes |
|---|---|
| Architecture and boundaries | Replaced arbitrary public provenance dictionaries with an explicit typed allowlist; negative tests reject private scenario, seed, threshold and manifest fields. |
| Data flow and contracts | Made engine/frame configuration and cached provenance access immutable or detached so external mutation cannot change an initialized trace. |
| Testability | Injected monotonic clock and wait dependencies into the runner without introducing a second scheduling framework. |
| Security | Fixed non-ASCII credential handling, HTTPS cookie flags, recursive input failures, expiry during slow socket I/O, and unexpected-error redaction. |
| Correctness and storage ownership | All writes now use the serialized PostgreSQL session that owns the advisory lock. Lost ownership permanently blocks writes; transient background reads share bounded retry/backpressure. Replayed old frames cannot move stream tails backwards; idempotency scopes include source identity. Actual PostgreSQL regressions terminate the owning backend and verify that no replacement writes occur. |
| Lifecycle and pacing | No-op speed/resume controls preserve pacing anchors. An authorized local bootstrap replaces obsolete demo cookies while deployed sessions keep their original run scope. |
| Acceptance coverage | Added executable retention/410 bounds, retained-run preservation, public SOC hysteresis/mode ordering and deadline-cancelled command tests. |
| Performance | Replaced per-row duplicate checks with bulk `RETURNING` plus one conflict comparison query per table. Preserved nominal pacing across ordinary I/O jitter while scheduling a full new interval after actual overload. Added a run/sequence index for snapshots. |
| Observability and operability | Added redacted, allowlisted request/batch timing and SQLSTATE fields, bounded backpressure/recovery logging, safe terminal diagnostics, preparation progress and visual resync counters. |
| Hygiene | Removed a redundant configuration branch, aligned the validation handler's annotation with both supported exception classes, corrected operation/session documentation and formatted the complete Python tree. The final container includes the lockfile used by private run provenance. |
| Cross-module viewer consistency | Added committed `status_revision` ordering for same-tick lifecycle races; resync requests the bounded 41-frame history. Deduplicated concurrent bootstrap, reset Cesium state on run change and fenced stale asynchronous responses. |

The explicit schema revisions were applied to fresh PostgreSQL databases, rolled back and reapplied.
Independent database reflection confirmed that all seven application tables, columns, primary/foreign keys, checks and indexes match the application metadata.
The second revision adds only the snapshot access index; the initial revision contains frozen DDL rather than importing live model metadata.

## Reproduce the Gates

From the repository root after following [Getting Started](../getting-started.md):

```bash
uv run ruff check backend/src backend/migrations tests scripts examples
uv run ruff format --check backend/src backend/migrations tests scripts examples
uv run mypy backend/src scripts/generate_contracts.py
uv run pytest -q
uv run python scripts/generate_contracts.py
npm --prefix frontend test
npm --prefix frontend run test:e2e
npm --prefix frontend run format:check
```

Use an isolated PostgreSQL database for integration and capacity tests; never point these setup fixtures at a production database.
Set `METIS_TEST_DATABASE_URL` to that isolated database when running `pytest` so the actual PostgreSQL checks execute.

The sustained workload uses a separate empty database and measures 12,000 simulated seconds across ten spacecraft:

```bash
docker compose exec -T db createdb -U metis metis_capacity
METIS_DATABASE_URL=postgresql+psycopg://metis:metis-local@127.0.0.1:55432/metis_capacity uv run metis-sim migrate
uv run python scripts/benchmark.py \
  --database-url postgresql+psycopg://metis:metis-local@127.0.0.1:55432/metis_capacity \
  --satellites 10 --duration 12000 --output docs/validation/throughput.json
```

Use a fresh database name for independent reruns.
The harness reports initialization separately, then exercises the actual paced writer, PostgreSQL commits, concurrent snapshot reads, controls and a visual WebSocket consumer.
Its HTTP/WebSocket clients use the in-process ASGI adapter; this is not a network or graphics benchmark.
The independent browser report records native Cesium rendering and real loopback transport.

## Limits of the Result

This is a deterministic synthetic engineering demonstration, not a flight-validated digital twin.
It uses central gravity plus fixed-axis J2, pinned Earth orientation, a spherical eclipse limb, ideal prescribed panel pointing and a bounded bus-energy model.
It omits drag, maneuvers, battery electrochemistry, attitude control dynamics and mission-calibrated sensors.
Cesium's illustrative day/night lighting is explicitly labeled approximate; backend illumination owns the power calculation.

The baseline derating leads to a state-driven reserve outcome at 20,650 simulated seconds; a matched healthy control avoids it.
Private outcome labels remain evaluator-only and are not a prediction generated by an AI model.
General SaaS tenancy/SSO, mission protocol adapters, TLE/SGP4 import, historical playback/seek and richer physical subsystems remain outside the specified P0 scope.

- [Operator Shift Log](shift-log.md): identity, migrations, private API, and handover verification.
