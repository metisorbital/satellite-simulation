---
title: Spacecraft Telemetry Validation
description: Executed numerical, persistence, export, and compatibility checks for the optional spacecraft telemetry extension.
content-type: reference
audience: engineering and ML teams
last-verified: 2026-09-26
---

# Spacecraft Telemetry Validation

The optional `spacecraft.v1` catalog emits 41 modeled channels and 12 explicitly missing channels at one-second simulated UTC intervals.
The [model and export guide](../reference/spacecraft-telemetry.md) defines equations, units, timing, provenance, and limitations.
The [sample inventory](../reference/sample-telemetry.md) records the provided spacecraft's telemetry families; those CSV measurements are not replayed or used to manufacture the synthetic values.

These results were measured on an Apple M3 Pro with 18 GiB RAM, macOS 26.6.2 arm64, Python 3.12, and an isolated PostgreSQL 17.6 container.
No new test files were added, following the current repository instructions. Existing suites and transient numerical/integration checks supplied the evidence below.

## Executed Checks

| Boundary | Result |
|---|---|
| Existing Python suite, including PostgreSQL cases | **186 passed, 1 skipped**, 132.22 s. The skipped check requires a working Dart executable. |
| Final focused contracts, service, persistence, and generated Dart compatibility checks | **43 passed, 1 skipped**, 5.38 s, after separating the persisted catalog mapping from the existing viewer descriptor. |
| Python hygiene | Ruff lint and format checks passed for 80 files; mypy passed for 51 application/generator files. |
| Generated contracts and documentation | All six schema/Dart artifacts reproduced without drift; the final strict documentation build passed in 3.43 s. |
| Existing Cesium numerical checks | **2 passed**; maximum independent subsecond position error remained `6.52669257278191e-7 m`. |
| Electrical conservation | Maximum measured battery terminal energy residual `4.12e-11 J`; charge/discharge losses are allocated once. |
| Thermal conservation | Maximum measured network residual `3.79e-10 J`; symmetric internal conduction cancels. |
| Attitude reference | 4,111 comparisons against independent SciPy rotations; maximum quaternion component discrepancy `3.33e-16`. |
| Angular-rate reference | 100 comparisons using independent DOP853 J2 trajectories; maximum discrepancy `2.24e-14 rad/s`. |
| Determinism and compatibility | 6,101 ticks checked across a quaternion sign transition; 359 fleet/speed isolation comparisons matched exactly; the original 15 channels retained their values. |
| Six-hour physical preparation | Three spacecraft, **64,803 physical samples**, prepared in **20.763 s**; temperatures `15.81775–85.10624 °C`; minimum adjacent quaternion dot product `0.999999849569467`. |
| Database, API, report, export, restart | A 120-second run containing two extended streams and one legacy stream produced **363 frames** with exact database/API/export/restart equality. |
| Migration | Fresh migration and upgrade from revision `0002` to `0003` passed on PostgreSQL; an existing legacy stream received `power-leo.v1`. |
| Export boundary and failure handling | A separate 502-frame paginated export respected the captured committed boundary and checksum. A missing frame caused failure without publishing a destination or leaving staging output. |
| Invalid physical configuration | A trajectory outside the supported thermal envelope returned HTTP `422` before any stream was published. |

The PostgreSQL round trip also checked a bounded report window, valid-only interval integration, zero-duration initial samples, payload schedule boundaries and eight completed images, battery voltage/current energy identity, quaternion norms, missing quality flags, mixed catalog identities, private-field exclusion, and rejection of unauthenticated or future-window requests.
The final catalog-mapping check confirmed that the public viewer descriptor keeps its existing shape while persistence, discovery, and reports retain each stream's catalog.

The local round-trip dataset had run ID `e9a843c7-f3ce-4bc7-85ae-135a895b1d02` and telemetry SHA-256 `0a5b43819e854825756cdcbea7e8454673b07529f1e645bfb0281f8a7b336b98`.
Run/stream IDs and emitted wall times change on a new execution; the hash identifies that particular validation artifact, not every deterministic regeneration.
The six-hour timing measures physical preparation only. It does **not** establish sustained database throughput for the extended catalog.

## Independent Review

Separate contributors reviewed the attitude model, electrical/thermal/payload models, and public catalog/report/export boundary.
Resolved findings included interval rail-voltage semantics, zero-power acquisition gates, SQLite transaction snapshots, rejection of future report starts, and retaining the existing public viewer descriptor.
Affected checks were rerun after corrections. The implementations remain small pure numerical components composed by each satellite; database and HTTP logic stay outside those models.

## Reproduce the Repository Gates

After [local setup](../getting-started.md), point `METIS_TEST_DATABASE_URL` at an isolated PostgreSQL database and run:

```bash
uv run ruff check backend/src backend/migrations tests scripts examples
uv run ruff format --check backend/src backend/migrations tests scripts examples
uv run mypy backend/src scripts/generate_contracts.py
uv run pytest -q
uv run python scripts/generate_contracts.py
git diff --exit-code -- schemas frontend/lib/api/generated.dart
npm --prefix frontend test
uv run zensical build --clean --strict
```

The generated-artifact drift command assumes the implementation has been committed.
Use the [telemetry guide](../reference/spacecraft-telemetry.md#read-reports-and-export-measurements) to create a run and export committed public measurements.
Transient numerical and round-trip checks above are measured implementation evidence, not additional committed regression coverage.

## Remaining Gates and Model Limits

Flutter analysis, compiled browser checks, and a rebuilt application image were not completed locally for this extension: the available Flutter installation needed a Dart SDK download that stalled.
The existing GitHub workflow contains those gates; a local Python or Cesium fixture pass does not establish their result.
The dashboard and inference path are deferred. The generated Dart change only adds optional public provenance fields.

There is no flight calibration, battery electrochemistry or thermal aging, resolved attitude controller, reaction-wheel dynamics, mission status decoder, or space-weather model.
Ideal LVLH pointing and independently Sun-tracking panels are explicit prescriptions; some reported quantities are consequently constant by assumption.
The default payload schedule ends before solar derating begins, so it is not an acquisition-failure experiment.
Training runs require deliberate scenario/configuration variation and separate evaluator truth, with complete runs kept together in dataset splits.
These checks establish behavior under the declared equations and data contracts; they do not establish predictive performance on an operating spacecraft.
