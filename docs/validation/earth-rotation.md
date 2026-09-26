---
title: Earth Rotation Validation
description: Local evidence for inertial camera framing, orbit paths, and Sun alignment.
content-type: reference
audience: engineering
date: 2026-09-27
---

# Earth Rotation Validation

The overview camera now holds its pose in GCRS while the Earth-fixed globe rotates beneath it.
Backend trajectory points include pinned Astropy GCRS-to-ITRS rotations.
The renderer interpolates those rotations and reconstructs the inertial orbit path from each point's own epoch.
Markers retain their original ITRS interpolation; lighting retains the backend ITRS Sun vector.
Eclipse, orbital propagation, and EPS equations are unchanged.

## Executed Checks

Local environment: Apple M3 Pro, macOS arm64, Flutter 3.47.5, Dart 3.13.4, Cesium 1.145.0, headless Chromium with SwiftShader.
No new test files were added.

| Check | Result |
|---|---|
| `uv run pytest tests/physics/test_frames.py tests/physics/test_environment_power.py -q` | 69 passed; expected invalid-time ERFA warnings. |
| `uv run pytest tests/physics/test_engine.py tests/contracts tests/test_dart_contracts.py -q -m 'not slow'` | 38 passed, 1 skipped, 1 slow gate deselected. |
| Ruff check/format and mypy on changed backend modules | Passed. |
| `uv run python scripts/generate_contracts.py` | Public schema and Dart regenerated from Python models. |
| `npm test` in `frontend` | 2 passed; maximum existing Hermite fixture error 6.53e-7 m. |
| `flutter analyze` and `flutter build web --release --no-web-resources-cdn` | Passed; existing Cupertino font-family warning remains. |
| `npm run test:e2e -- tests/browser/mission.spec.ts` | 1 passed, including controls and stale freeze. |
| `node --check frontend/web/globe.js` and `git diff --check` | Passed. |

An independent reviewer checked the backend matrices at 433 instants across 24 hours.
Position transforms agreed with the existing state adapter within 2.85e-9 m, orthogonality error was at most 7.78e-16, and eclipse fractions were identical after coordinate conversion.
No blocking interface or physics findings remained.

An additional browser inspection used 181 actual configured-orbit samples at 20-second spacing over one hour starting at 2026-01-01 UTC.
Earth orientation changed by 15.041019 degrees, consistent with sidereal rotation.
The camera's inertial position and direction stayed unchanged; maximum inertial path drift was 4.67e-9 m.
The satellite marker matched the backend sample exactly at the inspected midpoint.
The inertial Sun direction changed by 0.042449 degrees, consistent with its slow ephemeris evolution rather than Earth's daily spin.
Repeated paused-time updates preserved the camera transform.
Follow, exit-follow, zoom, reset, missing-data path hiding, and recovery completed without browser page errors.
The rendered globe, orbit, marker, and terminator were visually inspected.

## Limits and Handoff

This is local implementation evidence, not deployment evidence.
Restart the backend and reload the rebuilt web viewer together to receive the new required trajectory field.
The existing running demo process was preserved.
No live database migration, deployment, or full six-hour performance gate was performed.
Software-rendered browser diagnostics were about 1.5–4.8 FPS during inspection; this does not establish the 30 FPS demo-hardware gate.
Quaternion interpolation is presentation-only and bounded to available samples; missing orientation is disclosed rather than approximated.
J2 precession remains physical in simulated runs; configured archive orbits retain their existing two-body model limits.
