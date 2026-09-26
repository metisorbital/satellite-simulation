---
title: Use the Metis Simulation API
description: Discover satellite streams and consume durable telemetry and public events with safe replay cursors.
content-type: reference
audience: API consumers and developers
last-verified: 2026-09-26
---

# Use the Metis Simulation API

The API lets a monitoring system read committed satellite measurements without depending on the simulator's internal code. A **stream** is one satellite's numbered series of measurements within a **run**. Consumers discover a stream, request a page, process its items, then save the returned cursor to continue later. Public telemetry contains observed synthetic values; private scenario and outcome data require separate credentials.

For the full configuration and measurement definitions, use the [configuration and data contracts](contracts.md). This page describes the routes implemented in version `0.1.0`.

## Read and Replay a Local Stream

Complete [local setup](getting-started.md) first. In one terminal, start a demo paused after ten committed ticks:

```bash
uv run metis-sim demo --at 10
```

In another terminal, run the following from the repository root. It loads the ignored local credential file without displaying token values. Python parses the JSON, so no extra JSON command line tool is needed. The loopback bootstrap identifies this prepared demo run; the consumer token reads only public streams and frames.

```bash
set -a
. .local/runtime.env
set +a

base=http://127.0.0.1:8000
demo_run_id=$(curl -fsS "$base/v1/viewer/bootstrap" | uv run python -c \
  'import json, sys; print(json.load(sys.stdin)["run"]["run_id"])')
streams=$(curl -fsS "$base/v1/streams" \
  -H "Authorization: Bearer $METIS_CONSUMER_TOKEN")
stream_id=$(printf '%s' "$streams" | uv run python -c \
  'import json, sys; data = json.load(sys.stdin); print(next(item["stream_id"] for item in data["items"] if item["run_id"] == sys.argv[1]))' \
  "$demo_run_id")

page=$(curl -fsS -G "$base/v1/telemetry" \
  -H "Authorization: Bearer $METIS_CONSUMER_TOKEN" \
  --data-urlencode "stream_id=$stream_id" \
  --data-urlencode 'limit=3')
printf '%s\n' "$page"
cursor=$(printf '%s' "$page" | uv run python -c \
  'import json, sys; print(json.load(sys.stdin)["next_cursor"])')
curl -fsS -G "$base/v1/telemetry" \
  -H "Authorization: Bearer $METIS_CONSUMER_TOKEN" \
  --data-urlencode "stream_id=$stream_id" \
  --data-urlencode "after=$cursor" \
  --data-urlencode 'limit=3'
```

The first page contains frames 0–2 for one satellite; the second continues after that page. Outside the local demo, select the stream you need from `GET /v1/streams`; the loopback bootstrap is only used here to identify the current demo run. In an application, save `next_cursor` only after committing the frames you processed. On a restart, replaying a page is safe when you deduplicate by `(source_id, stream_id, sequence)`. See the [standalone consumer example](../examples/consumer.py) for a one-page polling pattern.

## Replay a Stream Safely

Omitting `after` starts at the earliest retained frame. `after=latest` starts at the current tail and returns an empty page with a cursor. Pass the previous `next_cursor` as `after` to continue. `GET /v1/telemetry` and `GET /v1/events` both require `stream_id`; `limit` defaults to 500 and allows 1–2,000 items. The response wrapper has this shape (values are illustrative):

```json
{
  "items": [],
  "next_cursor": "opaque-signed-cursor",
  "has_more": false,
  "retained_range": {"first_sequence": 0, "last_sequence": 10},
  "delivery_mode": "replay"
}
```

Each telemetry item follows [telemetry.v1](../schemas/telemetry.v1.schema.json), with `source_id`, `stream_id`, `sequence`, timestamps, and named `{value,quality}` channel readings. Event items follow [operational_event.v1](../schemas/operational_event.v1.schema.json) and use `event_sequence`. Cursors belong to one stream and one route: using a telemetry cursor for events or another stream returns `422`. Expired history returns `410` with retained bounds in `details`; start a deliberate resynchronization. An empty page keeps its cursor, so polling can resume later.

A telemetry item has this shape; the real demo includes more channels:

```json
{
  "schema_version": "telemetry.v1",
  "source_id": "metis-simulator-local",
  "stream_id": "00000000-0000-4000-8000-000000000001",
  "sequence": 0,
  "satellite_id": "METIS-01",
  "source_kind": "synthetic",
  "time_domain": "simulation_utc",
  "observed_at": "2026-09-21T00:00:00Z",
  "sample_window_s": 0,
  "emitted_at": "2026-09-23T00:00:00Z",
  "catalog_version": "power-leo.v1",
  "mode": "nominal",
  "interval_mode": "nominal",
  "channels": {"eps.battery_soc": {"value": 0.85, "quality": "valid"}}
}
```

The viewer's WebSocket can skip delivery frames while preserving committed history. Use the HTTP pages above for durable integration, and save a separate cursor for each stream and route.

## Authenticate Requests

Deployment-issued credentials use `Authorization: Bearer <token>`. `metis-sim init` writes distinct local role tokens to `.local/runtime.env`; keep that file out of commits and browser code. A local demo browser can obtain a scoped `metis_viewer` HttpOnly cookie from `GET /v1/viewer/bootstrap` only on loopback. When `METIS_PUBLIC_DEMO=1` and secure cookies plus an exact HTTPS origin are configured, that endpoint issues a read-only session for the server-owned shared demo. The bootstrap response includes `allowed_actions`; it is empty for public visitors. An authenticated operator can provision a run-scoped control session with `POST /v1/operator/runs/{run_id}/viewer-session` and an empty JSON object.

| Credential | Permitted work |
|---|---|
| Operator | Validate and create configurations, create and control runs, read public data and private manifests, provision viewer sessions. |
| Consumer | Read the catalog, streams, telemetry, and public events. |
| Evaluator | Read private truth and manifests. |
| Viewer session | Read public data for its one run and control that run. Control requests need its returned `csrf_token` in `X-CSRF-Token` and an allowed `Origin`. |

Every mutation **except configuration validation** needs a distinct ASCII `Idempotency-Key` of 1–128 characters. Retrying the same key with the same body returns the original result; reusing it with a different body returns `409`. Browser sessions expire after two hours by default. Never put operator, consumer, or evaluator bearer tokens into the browser.

## Find an Endpoint

All paths below are relative to `http://127.0.0.1:8000` in local development. The [interactive REST reference](http://127.0.0.1:8000/docs) and [generated OpenAPI JSON](http://127.0.0.1:8000/openapi.json) describe the running server's HTTP routes.

| Method and path | Credential | Purpose and request |
|---|---|---|
| `GET /health/live` | None | Confirm the process responds: `{"status":"alive"}`. |
| `GET /health/ready` | None | Check database and writer readiness; returns `503` when unavailable. |
| `GET /v1/catalog` | Operator, consumer, viewer | Read channel definitions; `version=spacecraft.v1` selects extended physical telemetry and omission selects `power-leo.v1`. |
| `POST /v1/configurations/validate` | Operator | Validate a complete `simulation.v1` JSON or YAML body without storing it. |
| `POST /v1/configurations` | Operator | Store a configuration revision; returns `configuration_id`, `canonical_hash`, and `schema_version` (`201`). |
| `POST /v1/runs` | Operator | Send `{"configuration_id":"...","retain":false}`; `retain` defaults to `false`. Returns public run status (`201`). |
| `GET /v1/runs/{run_id}` | Operator, scoped viewer | Read the latest durable run state and committed tick. |
| `POST /v1/runs/{run_id}/control` | Operator, scoped viewer | Send `{"action":"start"}`, `pause`, `resume`, or `stop`; use `{"action":"set_speed","speed":5}` for speed `1`, `5`, or `20`. Returns public run status. |
| `GET /v1/streams` | Operator, consumer, viewer | Discover stream IDs and retained ranges; a viewer sees only its run. |
| `GET /v1/telemetry` | Operator, consumer, viewer | Replay measurement frames using `stream_id`, optional `after`, and `limit` (default 500, maximum 2,000). |
| `GET /v1/events` | Operator, consumer, viewer | Replay public operational events with the same query parameters and separate cursors. |
| `GET /v1/runs/{run_id}/telemetry-report` | Operator, consumer, scoped viewer | Report committed coverage, quality counts, and statistics; optional inclusive `from_sequence` and `through_sequence`. |
| `GET /v1/runs/{run_id}/snapshot` | Operator, scoped viewer | Read committed status and frames; optional UTC `at` and `history` (1–41, default 1). |
| `GET /v1/runs/{run_id}/trajectory` | Operator, scoped viewer | Read orbit-only samples with `from`, `to`, and `step_s`; at most one hour and 3,601 points per satellite. |
| `GET /v1/evaluation/runs/{run_id}/truth` | Evaluator | Read private truth with `after` offset and `limit` (default 500, maximum 2,000). |
| `GET /v1/operator/runs/{run_id}/manifest` | Operator, evaluator | Read the private reproducibility manifest. |
| `GET /v1/viewer/bootstrap` | Scoped cookie or local loopback demo | Return `{csrf_token,run}` and issue or resume the viewer cookie. |
| `POST /v1/operator/runs/{run_id}/viewer-session` | Operator | Send `{}` with an idempotency key; set a run-scoped viewer cookie and return `{csrf_token,run}`. |
| `WS /v1/runs/{run_id}/visual` | Operator, scoped viewer | Receive bounded presentation updates; it is not the durable consumer feed. |

Configuration bodies are UTF-8, at most 1 MiB, and accept `Content-Type: application/json` or `application/yaml`. The [demo configuration](../configs/demo.yaml) is a complete input example. Public run status includes `run_id`, `status`, `epoch_utc`, `duration_s`, `committed_tick`, speeds, public satellite descriptors with `stream_id`, and model provenance. It omits scenario and seed information. The generated [public API schema](../schemas/public-api.v1.schema.json) defines its exact shape.

## Handle Errors and Live Updates

HTTP errors use one envelope:

```json
{
  "code": "invalid_cursor",
  "message": "Cursor is invalid.",
  "details": [],
  "request_id": "request-uuid"
}
```

Common statuses are `401` for missing or invalid credentials, `403` for a forbidden role or run, `404` for unknown resources, `409` for lifecycle or idempotency conflicts, `410` for expired replay history, `422` for invalid input, and `503` for unavailable persistence or readiness. `X-Request-ID` also identifies the request in response headers.

The visual WebSocket sends `visual.v1` messages containing `type`, `run_id`, `sent_at`, public `status`, `frames`, and per-stream `ranges`. Types are `snapshot`, `samples`, `clock`, `lifecycle`, and `resync_required`; the schema also reserves `error`. Reconnect and fetch a fresh snapshot after resynchronization. Use HTTP telemetry and events for durable consumption because the visual feed may coalesce frames.

For the design limits and privacy boundary, see the [specification](specification.md) and [contracts](contracts.md).

## Export Physics-Backed Telemetry for ML

The optional `spacecraft.v1` catalog adds electrical, thermal, payload, attitude, and magnetic-field measurements.
Streams retain their catalog version in storage; discover it through `GET /v1/streams` and fetch the matching catalog before interpreting frames.
The [spacecraft guide](reference/spacecraft-telemetry.md) provides a complete configuration, model limits, report semantics, and a command to export an unchanged, committed JSONL dataset with a checksum.
The [report JSON Schema](../schemas/telemetry-report.v1.schema.json) describes its public summary.
Private training labels remain behind the evaluator API and are not bundled with public measurements.
