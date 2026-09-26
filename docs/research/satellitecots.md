---
title: SatelliteCOTS Recorded Telemetry
description: Source assessment and integration boundaries for replaying BUPT-1 measurements.
content-type: reference
audience: engineering
status: implementation in progress
---

# SatelliteCOTS Recorded Telemetry

The [MobiCom24-SatelliteCOTS repository](https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS)
publishes measurements supporting
[Deciphering the Enigma of Satellite Computing with COTS Devices](https://arxiv.org/abs/2401.03435).
Its common telemetry table contains platform measurements from **BUPT-1**, one
12U CubeSat in the TianSuan project.
Atlas and Raspberry Pi computing payloads are devices on that spacecraft, not
additional satellites.

## Source Inventory

The full common CSV was profiled on 2026-09-26, without dropping rows or filling
gaps, from upstream commit `951b41521351d535b7c2354916d9c4991602e8c7`.

| Property | Measured value |
|---|---|
| Archive | `CommonData-Telemetries/telemetry_all.csv.zip` |
| Archive SHA-256 | `5d761d0bb65730cdbdb364f9c8706e9469bbbc6049cc0ed0b22d95ead8d656fa` |
| Compressed / CSV bytes | 80,884,357 / 1,562,405,581 |
| Records / numeric fields | 10,117,299 / 24 |
| First / last source time | 2023-03-22 04:12:37 / 2023-07-24 21:25:35 |
| Elapsed source seconds | 10,775,578 |
| One-second adjacent steps | 10,116,895 |
| Gaps / absent seconds | 403 / 658,280 |
| Largest adjacent step | 281,242 seconds, following 2023-07-14 11:54:01 |
| Duplicate / backwards timestamps | 0 / 0 |
| Empty or non-finite numeric readings | 0 |

The CSV timestamps have no explicit timezone suffix.
The importer interprets them as UTC based on the paper's UTC synchronization
description, and records this interpretation in provenance.
The paper's Table 2 reports mixed acquisition cadences: one second for bus,
payload and communications currents, three seconds for MPPT measurements, and
four seconds for battery and surface temperatures.
Repeated values in the merged table must not be described as new acquisitions
from every sensor each second.

There are many numeric zeros, particularly in payload temperatures and currents.
The source does not document a universal zero-as-missing sentinel, so replay
preserves those values and discloses this limit.
Both battery-current columns are negative throughout this release; their raw
signs are preserved independently without inferring a summed battery-power or
state-of-charge model.

Electrical source values are millivolts and milliamps; public channels convert
them to volts and amps.
Temperature channels retain degrees Celsius.
The public catalog keeps the individual battery, MPPT, computing-device and
communications measurements.
Overlapping bus voltage/current panels can use these readings directly.
Solar power and total consumed power follow the upstream
[`Energy-Overview` recipe](https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS/blob/951b41521351d535b7c2354916d9c4991602e8c7/Energy-Overview/plot-section4-figure10.py),
with explicit snapshot-derived semantics rather than an assumed interval mean.

## Represent the Recorded Mission

Use one `BUPT-1` spacecraft in one TianSuan display grouping.
Keep the existing configurable constellation for physics runs.
Replicating one recorded stream into several spacecraft would misrepresent the
number of independently observed vehicles.

The source contains platform telemetry and separate computing experiments,
including terrestrial measurements.
The shared satellite telemetry table is the replay source; terrestrial
benchmarks must not be presented as in-orbit telemetry.
Per-channel cadence and data gaps must be measured from the source and described
alongside the imported catalog rather than assuming a uniform one-second grid.

## Keep Storage and Playback Separate

Import the source into immutable dataset/chunk tables with its upstream commit,
content checksum, source columns, original timestamps and ordered row identity.
Keep these records separate from generated run history and its retention policy.
Reimporting the same verified source must not duplicate data.
Store bounded, indexed compressed CSV blocks in Postgres: expanding more than
ten million rows into full JSON telemetry envelopes would unnecessarily exceed
the demo database's capacity.
Every original row remains available through the dataset reader.

Each playback creates a fresh run and stream, beginning at sample zero.
Read source records from Postgres in bounded batches, pace delivery by the
recorded time axis, and append the emitted public frames through the existing
transactional run pipeline.
Pause, resume, speed changes, durable consumer cursors and viewer transport remain
shared with physics runs.
The terminal dataset sample completes playback; a new run starts over.
An Overview timeline selects a source time; seeking allocates a fresh playback
stream at the next available original sample.
Seeking does not rewrite existing frames or publish future data in the previous
run's consumer stream.

Public records retain `source_kind=observed` and their original observation time.
Stream sequence counts emitted measurements; it must not be mistaken for elapsed
seconds when the source has gaps.
Do not interpolate missing measurements, infer operating mode, invent orbital
coordinates, or derive state of charge from an unsupported battery model.

## Preserve the Viewer

Add a physics/recorded source choice before starting a run.
Reuse existing dashboard panels where their channel meanings match the source.
Add panels for measured fields that the existing dashboards do not cover.
Keep every existing dashboard available and label unsupported measurements as
unavailable.
The globe must not display a synthetic orbit as if it were measured.

## Verify the Integration

Acceptance requires a reproducible source inventory, an idempotent import with
database readback, timestamp-faithful playback, reset to sample zero, source
switching, and retained physics behavior.
Verify the local and Render databases independently.
Code availability in a pull request and data availability in Render Postgres do
not establish that the deployed application contains the new source selector.

See the [data contracts](../contracts.md),
[database reference](../reference/database.md), and
[Flutter viewer](../frontend.md) for the existing interfaces.
