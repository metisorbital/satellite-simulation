---
title: Replay Recorded Satellite Data
description: Import the complete BUPT-1 corpus into Postgres and control recorded playback in Flutter.
content-type: guide
audience: operators and developers
---

# Replay Recorded Satellite Data

METIS can produce physics telemetry or replay observed BUPT-1 measurements from
Postgres. Both sources use the existing run controls, public telemetry stream,
consumer cursors and Flutter dashboards.
The [source inventory](research/satellitecots.md) describes the spacecraft,
timestamps, gaps, units and unsupported measurements.

## Choose and Play a Source

1. Sign in to the Flutter viewer.
1. Before starting a run, choose **Real data** in the **Data source** control.
1. Open **Overview** to see the recorded mission and timeline.
1. Press **Start run** to play from the first source record, at one source second
   per wall-clock second. Pause, resume and the existing speed controls also work.
1. Open **Telemetry** to use the existing dashboards and the additional recorded
   channel panels. Unsupported measurements remain unavailable.

The Overview timeline covers the full archive. Move its slider and apply the
position, or choose the first or last point. Press **Start run** after applying
a new position. If the chosen time falls inside a recording gap, the position
snaps forward to the next original observation and shows the actual selected
time. Reset returns recorded playback to the beginning.

The source has no measured orbit, attitude, spacecraft mode or battery state of
charge. The existing Earth Overview remains available. Its BUPT-1 orbit is
configured from the operator's published altitude and inclination, with explicit
orientation and phase assumptions. The globe follows the same replay clock and
speed as recorded telemetry. Its modelled position stays separate from observed
channels. The dataset timeline sits below the Earth; the existing telemetry
history controls remain available. Switching back to **Physics simulation**
restores the configured synthetic constellation and its existing displays.

Use **Settings → Edit constellation** to adjust BUPT-1's modelled orbital
elements. The initial configuration uses the published altitude range
487.607–494.651 km and inclination 97.3710°. Its source and missing orientation
assumptions appear with the orbit fields. Saving creates a fresh replay at the
archive beginning. Subsequent seek and reset operations preserve those elements.
The recorded spacecraft's identity and membership stay fixed; Atlas and Raspberry
Pi channels describe payload devices on BUPT-1, not additional satellites.

Every playback or seek creates a fresh run and stream. Existing recorded history
stays immutable, and future source values are not published into an earlier
stream. The last source record completes playback; it does not loop silently.
An interrupted service follows the existing aborted-run recovery policy; reset
or choose a new source position to begin another playback.

## Import the Complete Source

From the repository root, download the pinned archive into ignored local storage:

```bash
mkdir -p .local/datasets
curl --fail --location \
  https://raw.githubusercontent.com/TiansuanConstellation/MobiCom24-SatelliteCOTS/951b41521351d535b7c2354916d9c4991602e8c7/CommonData-Telemetries/telemetry_all.csv.zip \
  --output .local/datasets/telemetry_all.csv.zip
uv run python -m metis_sim.import_satellitecots \
  --archive .local/datasets/telemetry_all.csv.zip --dry-run
```

Preparation verifies the pinned archive and complete CSV checksums, all source
columns, numerical values, timestamps and row count. It produces reusable
lossless compressed blocks without contacting a database.

Select the target database through `METIS_DATABASE_URL`, apply the migrations,
then import. For the repository's local Compose database:

```bash
export METIS_DATABASE_URL=postgresql+psycopg://metis:metis-local@127.0.0.1:55432/metis
uv run metis-sim migrate
uv run python -m metis_sim.import_satellitecots \
  --archive .local/datasets/telemetry_all.csv.zip
uv run python -m metis_sim.import_satellitecots \
  --archive .local/datasets/telemetry_all.csv.zip --verify-only
```

The import is atomic and uses a dataset-specific advisory lock. Readers discover
the dataset only after its complete import commits. Every stored block is read
back and the full original CSV checksum is reconstructed. Running the import
again verifies the existing corpus without duplicating or overwriting it.
Use `--database-url-env NAME` when the connection is supplied under a different
environment variable. Credentials are never printed by the importer.

## Provision Render Safely

Use the same pinned preparation and importer against the existing Render
Postgres instance. Keep credentials in the process environment and preserve the
existing network access policy. Importing data does not deploy the application.

If the live application already contains revision `0006`, run its normal
migration command before import. If the deployed code only knows revision
`0005`, provision the exact additive storage operations from `0006` without
advancing `alembic_version`. Advancing that marker while the old image is live
would prevent its migration command from resolving the new revision on restart.
The new migration validates and adopts matching preprovisioned tables when the
updated image is deployed. Never stamp an unknown revision into the old app's
database merely to make an import command run.

The entire source stays compressed in Postgres. Playback reads bounded blocks and
stores only emitted run frames in the public log. Existing run-history retention,
capacity limits and browser session limits still apply; the compressed archive
does not make months of expanded playback history fit into a small demo database.
Imported source blocks are independent of ordinary run-history expiration.

See [validation evidence](validation/recorded-data.md) for the actual targets,
readback results and deployment boundary from this implementation.
