---
title: Flutter Migration Validation
description: Scope and current verification of the Flutter web migration and generated Python references.
content-type: reference
audience: maintainers
---

# Flutter Migration Validation

The September 23, 2026 migration replaces the React application with Flutter web.
Cesium remains a local rendering dependency. The backend numerical model, persisted
telemetry contract, and scoped session boundary are preserved.

## Python and Generated Documentation

Verification ran on an Apple M3 Pro with 18 GiB RAM, macOS 26.6.2 arm64,
Python 3.12.12, and Flutter 3.47.5 / Dart 3.13.4.
The local SDK used for these checks is `/tmp/metis-flutter`; add its `bin` directory
to `PATH` to repeat the Flutter commands in this checkout.

| Check | Result |
|---|---|
| Existing backend suite, `uv run pytest -q` | 166 passed, 6 skipped in 170.34 seconds. Optional PostgreSQL checks were not enabled for this run. |
| Generated Dart contracts, `uv run pytest tests/test_dart_contracts.py -q` with `DART_EXECUTABLE` set | 5 passed, including actual Dart execution on observed-source telemetry and nullable/vector/event payloads. |
| Ruff lint and format | Passed across backend, migrations, tests, scripts, and examples. |
| mypy | Passed across 40 source files, including the contract generator. |
| `uv run zensical build --strict` | Passed; generated class/function/method anchors and NumPy sections inspected. |
| API-reference coverage | All 33 backend modules and their public top-level classes/functions render across six reference pages. |
| Browser documentation inspection | `SimulationEngine` class, parameter table, source reference, and cross-linked types visible in the local Zensical preview. |

The generated JSON Schemas remain unchanged. Dart types are generated only from
public response/request models; private configuration and scenario classes do
not enter the Dart output. A separate reviewer inspected schema conversions and another reviewed the build
integration and mission lifecycle. The live browser check caught a Dart-to-JavaScript
bit-shift bug in the idempotency-key random bound; the bound was corrected and real
control acknowledgements retested successfully.

## Flutter and Globe Checks

| Check | Result |
|---|---|
| Flutter playback tests | 10 passed: committed clamp/stale freeze, pause and status ordering, run replacement, bounded history, future/wrong-stream rejection, buffer intersections, gaps, disconnect, and invalid scalar handling. |
| Flutter analyzer | Passed without issues. |
| Flutter web build | Release build passed, including the WebAssembly compatibility dry run. |
| Browser suite | 3 passed in 44.2 seconds: controls and auth headers, selection/camera/dialog, offline assets, stale freeze, delayed old-run response, and WebGL fallback. The smoke test reported zero external requests and page errors. |
| Live backend browser check | PostgreSQL readiness passed; Flutter rendered real data, selected METIS-02, changed speed to 5×, resumed advancing telemetry, paused at tick 65, and followed the selected spacecraft. |
| Cesium numerical and resync tests | 2 passed; maximum Hermite error 6.5267e-7 metres against the independent dense orbit fixture, plus late sample insertion after a newer sequence. No tolerance was relaxed. |
| Docker configuration | `docker build --check .` passed without warnings. |
| Final container build | `docker build -t metis-simulation:flutter-local .` passed on Linux ARM64; final release compilation took 106.9 seconds. |
| Image runtime packaging | Ephemeral Python container ran as UID 10001 and verified the configured `/app/frontend/build/web` path, compiled Dart, bootstrap, Cesium, Earth imagery, and CanvasKit assets. |

Browser tests run with one worker because simultaneous software WebGL contexts
compete for rendering resources. Tests use synthetic HTTP/WebSocket fixtures; the
separate live check above exercised actual PostgreSQL-backed control acknowledgements.

The verified image is `sha256:0dd7f6e962ce6109ca5c1b1b6edc7f2b950742a537374447c40a6c479d86a7ba`.
Flutter emitted a nonfatal Cupertino font-family warning during container compilation;
the current interface uses bundled Material icons. This local image check was ARM64;
the updated GitHub Actions workflow was not executed remotely during this change.

## Evidence Boundaries

The earlier [browser report](browser.md) and frontend FPS figures in
[throughput evidence](throughput.md) apply to the previous React viewer.
They do not establish Flutter frame rate or a new capacity result.
No production deployment or publication is part of this migration.
