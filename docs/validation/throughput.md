# Sustained capacity evidence

The ten-spacecraft run completed **120,010 frames with zero sequence gaps** in **603.349885 wall seconds**, sustaining **19.888957×** and **198.889571 frames/s** at requested 20×.
The strict 20× completion gate was **not met**: its predefined allowance was 600.25 seconds.
The supported measured maximum tier on this machine is therefore **ten spacecraft at approximately 19.89× effective speed**, with 20× still being the requested pacing setting.
This follows the explicit reduced-tier handoff allowed by NFR-01; the original failed timing gates remain intact in the [machine-readable result](throughput.json).

## Recorded workload and environment

The run started at `2026-09-22T22:14:08.908513Z` and durably completed at `2026-09-22T22:24:12.258398Z` (2026-09-23 in Asia/Yerevan).
Its run ID is `39d4ce99-2b75-446c-b1a9-d9b1acb089d0`.
It used ten healthy spacecraft with distinct initial anomalies, a 12,000-second duration, one-second physical/telemetry steps, and actual PostgreSQL commits.
Initialization took 9.5766 seconds and is reported separately from paced throughput.

- Apple M3 Pro, 11 physical/logical CPU cores, 18 GiB RAM, macOS 26.6.2 arm64.
- Python 3.12.12; dependencies pinned by `uv.lock`; PostgreSQL 17.6 in local Docker.
- A fresh, migrated `metis_capacity` database; other unrelated local services were left running.
- Backend source SHA-256: `5d3f63816ef0c99a60cf578422a044ba939c6bd62c090d3d5cecbd364221d62a`, independently matched to the delivered source after the run.

## Results

| Measurement | Result |
|---|---:|
| Terminal state / simulated endpoint | completed / 12,000 s |
| Streams / expected streams | 10 / 10 |
| Frames / expected frames, including t=0 | 120,010 / 120,010 |
| Per-stream sequences | Every integer from 0 through 12,000 |
| Effective speed / requested speed | 19.888957× / 20× |
| Sustained newly advanced frames | 198.889571/s |
| Snapshot reads | 1,156 |
| Read p95 / maximum | 32.89 / 283.15 ms |
| Control acknowledgements | 20 |
| Control p95 / maximum | 45.73 / 67.78 ms |
| Benchmark process peak RSS | 236,519,424 bytes (225.56 MiB) |
| Final database size | 372,116,627 bytes |
| Mean serialized public payload | 1,579.54 bytes/frame |
| Host free storage at completion | 44,739,973,120 bytes |
| Visual messages / terminal endpoint received | 2,531 / tick 12,000 |
| Visual transport errors | 0 |

Both latency p95 values are below the 500 ms requirement.
The payload measurement is JSON text size; database size includes indexes, private truth and run metadata.
RSS covers the Python benchmark process, excluding PostgreSQL/Docker and the separately measured browser.

The [operational log summary](throughput-operations.json) contains 121 sampled batch observations: p95 commit time 63.52 ms, maximum 110.60 ms; p95 processing time 19.02 ms, maximum 65.28 ms.
Sampled command-queue depth stayed zero, and no persistence-backpressure, runner-failure or visual-resynchronization events were logged.
These timings sample roughly one batch per hundred simulated ticks; they do not capture every possible latency outlier or prove a specific cause for the speed shortfall.
The writer has one synchronous frozen batch at a time, bounded to four ticks and forty frames for this workload; it has no accumulating telemetry commit queue.

## Measurement boundary and reproduction

The required three-spacecraft demo tier passed a separate one-wall-minute check with the same frozen backend and fresh PostgreSQL database.
It completed 1,200 simulated seconds in **60.060870 wall seconds** (19.979731×), within the original 60.25-second allowance, with all **3,603 frames** and zero sequence gaps.
Read p95 was **17.78 ms**, control p95 **37.36 ms**, and the visual consumer reached the terminal tick.
All gates passed in [the three-spacecraft result](throughput-demo.json).
To reproduce, use a fresh migrated database and the same harness with `--satellites 3 --duration 1200 --output docs/validation/throughput-demo.json`.

The harness uses the real paced runner and PostgreSQL, concurrent snapshot reads every approximately 0.5 wall seconds, speed-control acknowledgements every approximately 30 seconds, and an authenticated visual stream through completion.
Its HTTP/WebSocket clients run through Starlette's in-process ASGI adapter; the latency numbers exclude a network link.
Read polling finishes after durable completion, so the report uses the persisted terminal timestamp rather than the later polling timestamp to measure paced duration.

See the [validation index](README.md#reproduce-the-gates) for the exact fresh-database commands.
The harness exits nonzero for the strict timing miss; that result is preserved rather than relabeled as a 20× pass.
The original 0.25-second allowance combines the maximum 0.2-second batch interval with one 0.05-second scheduling interval and was fixed before this sustained run.

The [independent browser measurement](browser.md) achieved 60.06 actual Cesium scene renders/s with ten positioned spacecraft, zero stale/missing readings, and selected-sample lag below one simulated second over a 15-second native-renderer observation.
That observation used real loopback transport and was performed separately from the ten-minute backend test.
Neither result guarantees performance on other hardware, during camera motion, under software rendering, or over a remote deployment.
