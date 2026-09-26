---
title: Recorded Satellite Replay Validation
description: Measured source, Postgres import, replay, and Flutter verification for SatelliteCOTS.
content-type: reference
audience: engineering and operators
date: 2026-09-26
---

# Recorded Satellite Replay Validation

This extension adds the pinned SatelliteCOTS corpus as an observed source alongside
the existing physics simulator. The [source inventory](../research/satellitecots.md)
and [operator guide](../recorded-data.md) define its interpretation and use.

## Source and Database Evidence

The complete archive at upstream revision
`951b41521351d535b7c2354916d9c4991602e8c7` contains **10,117,299 records** from
one BUPT-1 spacecraft, with 24 numeric source fields. Its original CSV SHA-256 is
`800787c7ed5cf8687b4c5d83388857323a4c2ed29965067764c0f656eaf340be`.
The first observation is `2023-03-22T04:12:37Z`; the last is
`2023-07-24T21:25:35Z`. There are 403 source gaps, representing 658,280 absent
seconds; playback does not invent values inside them.

Lossless preparation produced 2,471 bounded chunks totaling 81,147,189 compressed
bytes. Local Postgres imported every chunk atomically. Full database readback
reconstructed the original CSV checksum, and a separate `--verify-only` invocation
returned `verified: true`, `inserted: false`, and the same complete row count.
The two source tables and indexes occupy 86,827,008 bytes locally. Original source
rows remain separate from normal run-history retention.

The local application database was at Alembic `0005`. Exact additive operations
from migration `0006` provisioned source storage while preserving that marker so
the older application can restart. A fresh isolated database migrated normally
through `0006`; invoking the same operations again adopted the matching tables
without changing data or revision. The new application migration validates
preprovisioned table columns, types, keys, checks, indexes and immutable triggers.

Render production Postgres `satellite-simulation-db` received the same complete
corpus. Full readback reconstructed the same CSV checksum across all 2,471 chunks,
and independent indexed reads returned original sequences 0, 5,304,438 and
10,117,298 at the beginning, middle and end. Import plus readback took 461.82
seconds over the external connection. Source tables and indexes occupy
86,827,008 bytes; total database size after import was 100,234,931 bytes. Its
existing `0005` migration marker was preserved pending application deployment.
The temporary single-client access rule was removed and the original empty
external allowlist was independently read back. The deployed application's
`/health/ready` endpoint still returned HTTP 200 with `status: ready` afterward.

## Replay and Contract Evidence

A direct service/API rehearsal used actual source rows around the first gap,
normalized to offsets `0, 1, 3, 4`. At source second two, only the first two
observations existed: sequence and elapsed time were not conflated. Pause held
the clock; resume completed at elapsed four with four observations and no private
physics truth. An inclusive source-time history window returned the correct
observations after the gap.

Seeking into the gap snapped to the observation at offset three in a fresh run
and stream, whose first emitted sequence was zero and whose epoch remained the
original dataset epoch. Seeking a running replay back to zero safely replaced
it. Unknown dataset selection failed without replacing the active run. Switching
back to physics restored the configured three-spacecraft mission.

The first real observation projects to bus voltage `16.035 V`, bus current
`1.509 A`, consumed power `24.196815 W`, and solar power `19.40235 W`. Independent
battery current remains signed (`-0.16 A` for battery one). Unsupported orbit,
attitude, mode and state of charge remain unavailable. Derived source snapshots
are explicitly distinct from simulator interval means.

## Executed Gates

On Apple M3 Pro / arm64, macOS 26.6.2, Python 3.12, Flutter 3.47.5:

| Gate | Result |
|---|---|
| Existing Python suite with isolated real Postgres and Dart generation | 206 passed in 132.96 seconds; five expected warnings |
| Ruff lint and format | Passed |
| Mypy | 64 source files passed |
| Existing Flutter tests | 18 passed |
| Flutter analyzer | Passed |
| Flutter release web build with bundled assets | Passed; existing Cupertino font warning |
| Existing Node interpolation and resync checks | 2 passed; interpolation maximum error unchanged at 6.52669257278191e-7 m |
| Existing compiled-browser cases | 6 passed in 42.7 seconds after aligning stale selectors with existing UI |
| Strict documentation build | Passed |
| Docker application build | Passed; final orbital presentation receives a subsequent build in CI |

The database test target was `metis_cots_validation_20260926`, separate from the
application database. No new automated tests were added, as requested. Existing browser selectors and
schedule-preservation expectations were brought into line with the current
Overview, settings and operator menus. Existing
checks and focused manual failure-path exercises supply the evidence above.

## Independent Reviews

Separate owners reviewed source interpretation, import/storage, the replay
adapter/API, and the Flutter timeline. Findings corrected before handoff include:

- Atomic cache publication across runner/API threads, missing committed-chunk
  detection, cached time-bound validation, and strict dataset provenance checks.
- Source-time report/history filtering, sparse replay sequence handling, observed
  stream discovery, and public provenance allowlisting.
- Timeline success feedback only after successful reconnection, preserving the
  user's target on transport failure, and accurate clock wording across gaps.

## Deployment Boundary

The pull request contains the application changes. Importing the source into
Render Postgres does not deploy the source selector or timeline to the live
application. Those controls become available after this branch is merged and the
updated application is deployed. Physics remains an independent selectable source.

The data supports replay and downstream alert consumers. This change does not
implement future METIS alert rules or action policies, infer missing spacecraft
state, or validate the dataset as a flight operations safety system.
