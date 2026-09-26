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

Import the source into immutable dataset/sample tables with its upstream commit,
content checksum, source columns, original timestamps and ordered row identity.
Keep these records separate from generated run history and its retention policy.
Reimporting the same verified source must not duplicate data.

Each playback creates a fresh run and stream, beginning at sample zero.
Read source records from Postgres in bounded batches, pace delivery by the
recorded time axis, and append the emitted public frames through the existing
transactional run pipeline.
Pause, resume, speed changes, durable consumer cursors and viewer transport remain
shared with physics runs.
The terminal dataset sample completes playback; a new run starts over.

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
