---
title: Storage, Producer Contract, and Delivery Research
description: Research and decision rationale for the source-neutral telemetry log, storage engine, replay semantics, and private simulation truth.
content-type: research
audience: engineering
status: implementation input
date: 2026-09-21
---

# Storage, Producer Contract, and Delivery Research

## 1. Recommendation

Use one Python service and one PostgreSQL database for P0. Keep the simulator behind a `TelemetrySink`-style application boundary, validate its domain messages with Pydantic, append committed events to an immutable PostgreSQL log, and expose cursor-based HTTP reads plus a disposable WebSocket projection. Do not add MQTT, NATS, TimescaleDB, InfluxDB, ClickHouse, or a separate ingestion service for the hackathon.

The durable boundary is a source-neutral event envelope. Its identity is:

```text
source_id + event_id                       event identity and retry deduplication
source_id + stream_id + satellite_id + sequence
                                             producer order and collision detection
```

`simulation_run_id` is deliberately absent from this identity. A simulation run owns a `stream_id` through control-plane metadata; a future ground receiver, file importer, or mission adapter can create the same event shape without inventing a simulation run.

The selected split is:

```text
validated YAML / future JSON API
             |
       frozen run manifest ---- private scenario manifest
             |                           |
       deterministic simulator      truth schema
             |
       source-neutral events
             |
       PostgreSQL append log ------ consumer HTTP replay
             |
       latest-state projector ------ bounded WebSocket ------ viewer
```

This applies KISS and SRP at boundaries that matter: simulation physics produces facts, the log preserves facts, presentation projects facts, and private truth evaluates outcomes. It does not turn each responsibility into a separately deployed service.

FastAPI is a practical external boundary because request models are validated and included in generated JSON Schema and OpenAPI. Pydantic can generate JSON Schema Draft 2020-12 / OpenAPI 3.1 schemas from the same models. That makes one model family usable for YAML validation, the later JSON API, and published contract artifacts without hand-maintained duplicate schemas ([FastAPI request bodies](https://fastapi.tiangolo.com/tutorial/body/), [Pydantic JSON Schema](https://docs.pydantic.dev/latest/concepts/json_schema/)).

## 2. Workload sizing

P0 emits one **frame row per satellite per simulated telemetry tick**, not one row per metric. With:

- `N` satellites,
- simulated sampling frequency `f` frames/satellite/simulated-second, and
- pacing multiplier `A` simulated-seconds/wall-second,

the paced write rate is:

```text
frames per wall second = N * f * A
frames per wall day    = N * f * A * 86,400
```

The baseline is `f = 1 Hz simulated`, three demo satellites, 1–10 configurable satellites, and a 20x target. It makes no 100x performance promise.

| Scenario | Frames/wall second | Frames/10-minute demo | Frames/continuous wall day |
|---|---:|---:|---:|
| 3 satellites, 1x | 3 | 1,800 | 259,200 |
| 3 satellites, 20x demo | 60 | 36,000 | 5,184,000 |
| 10 satellites, 1x | 10 | 6,000 | 864,000 |
| 10 satellites, 20x P0 maximum | 200 | 120,000 | 17,280,000 |
| 100 satellites, 1x future case | 100 | 60,000 | 8,640,000 |
| 10 satellites, 100x non-goal | 1,000 | 600,000 | 86,400,000 |

With 50 metrics in each frame, the P0 maximum still writes 200 database rows/s, carrying 10,000 scalar values/s. A narrow one-row-per-metric design would instead write 10,000 rows/s and 864 million rows per continuous wall day. This is the decisive reason to keep an atomic, wide frame.

These calculations are capacity inputs, not throughput evidence. Before claiming the 10-satellite target, run the real schema and payload on named hardware, record p50/p95 commit latency, sustained frames/s, queue depth, database size, and replay speed. An offline unpaced run is sink-limited and is not described by the pacing formula.

## 3. Storage choice

### 3.1 Selected: plain PostgreSQL

PostgreSQL holds all P0 concerns without a second operational dependency:

- relational run/configuration administration;
- immutable event envelopes and idempotency constraints;
- private truth with separate grants;
- consumer cursor queries;
- flexible but predictable frame payloads in `jsonb`;
- transactions for batch append and optional delivery state.

PostgreSQL recommends that JSON documents retain a predictable structure and represent an atomic datum. It also notes that `jsonb` supports indexing and avoids reparsing stored JSON. One telemetry frame is an atomic datum and matches that guidance ([PostgreSQL JSON types and document design](https://www.postgresql.org/docs/current/datatype-json.html)). Keep identities, timestamps, type, and sequence in typed columns; keep the versioned frame data in `jsonb`. Do not put the entire envelope into an unindexed JSON blob.

Start with one unpartitioned log plus the indexes below. PostgreSQL's own guidance says partitioning pays off when a table becomes very large and that the threshold depends on the application; it offers range partitioning and fast detach/drop maintenance when that threshold is reached ([PostgreSQL table partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)). The short demo is tens of thousands of frames, so partition maintenance is premature.

If partitioning is later justified, use `ingested_at` for retention-oriented partitions. Simulation `observed_at` can be accelerated, historical, future-dated, or replayed and is therefore a poor operational retention clock. Keep an index on `(source_id, stream_id, satellite_id, observed_at)` for time-series access.

### 3.2 Upgrade option: TimescaleDB

TimescaleDB remains the lowest-friction storage upgrade because its hypertables remain PostgreSQL tables and automatically create time-range chunks. Its current storage model can keep recent chunks row-oriented and move older chunks to columnar storage ([Timescale hypertables](https://docs.timescale.com/use-timescale/latest/hypertables/)). Consider it only when measured retention, compression, downsampling, or long-range query costs dominate engineering time. It does not change the producer contract.

### 3.3 Not selected for P0: InfluxDB 3

InfluxDB 3 has a native time-series model with time, tags, and fields and writes line protocol over HTTP ([InfluxDB 3 write model](https://docs.influxdata.com/influxdb3/core/write-data/)). Its schema guidance warns against wide and sparse tables and recommends homogeneous rows ([InfluxDB 3 schema design](https://docs.influxdata.com/influxdb3/core/write-data/best-practices/schema-design/)). It would still require a relational/control store for frozen manifests, lifecycle transitions, exact sequence collision rules, and private truth. Adding two stores does not buy a demonstrated P0 need.

It also has product/version-specific duplicate-point semantics tied to time and tags, which is a different identity from the required source/stream/sequence contract. An adapter could target Influx later, but it should not define producer identity.

### 3.4 Not selected for P0: ClickHouse

ClickHouse becomes relevant when a measured analytical workload requires a separate scan-optimized replica. Its current documentation recommends batches of at least 1,000 rows, ideally 10,000–100,000, and about one synchronous insert per second to control part creation and merge load ([ClickHouse bulk inserts](https://clickhouse.com/docs/optimize/bulk-inserts)). That is compatible with a future batch exporter, not a reason to make ClickHouse the run-control and event-identity database for a 60–200-frame/s hackathon source.

### 3.5 Storage decision triggers

Revisit the decision only with measurements:

| Evidence | Likely response |
|---|---|
| PostgreSQL table/index maintenance or retention becomes operationally costly | Native range partitioning, then TimescaleDB if automation/compression is valuable. |
| Long-range analytical scans compete with ingestion after indexing and rollups | Replicate/export committed frames to ClickHouse or object storage. |
| Existing operations mandate InfluxDB and its schema fits the stable metric set | Add an output adapter; preserve the source-neutral envelope upstream. |
| A downstream system needs independent durable subscriptions | Add an outbox relay and broker; do not put broker types in simulator domain models. |

## 4. Durable event contract

### 4.1 Envelope

The envelope borrows CloudEvents' useful identity separation but does not require a CloudEvents SDK. CloudEvents defines `source + id` as unique for an occurrence, permits the same ID for a retry, and distinguishes occurrence `time` from identity ([CloudEvents 1.0 specification](https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md)). Use the following required fields:

| Field | Type | Semantics |
|---|---|---|
| `event_id` | UUID string | Opaque occurrence ID. A retry preserves it. |
| `event_type` | string | `metis.telemetry.frame.v1` or another registered event type. |
| `schema_version` | integer | Envelope/data major version; `1` for P0. |
| `source_id` | string | Stable producer installation or adapter identity. |
| `stream_id` | UUID string | Ordering epoch. Create a new stream whenever sequence state resets. |
| `satellite_id` | string | Stable mission/entity identifier, independent of source. |
| `sequence` | non-negative integer | Strictly increasing per `(source_id, stream_id, satellite_id)`; gaps are allowed and observable. |
| `observed_at` | RFC 3339 UTC timestamp | Simulation UTC for synthetic frames; source observation UTC for real data. |
| `origin` | enum | `simulated` or `observed`. Replay does not rewrite origin. |
| `producer` | object | Producer name/version and adapter/model version where applicable. |
| `data` | object | Event-type-specific payload. |

The ingest service adds `ingested_at` and `log_offset`; producers must not supply either. `log_offset` is delivery order, not physical or causal time.

Do **not** model `replay` as an origin. A replayed frame remains simulated or observed. The response or transport metadata carries `delivery_mode: replay`, and a regenerated derivative uses a new stream plus `derived_from` provenance. This prevents downstream consumers from losing the actual origin of data.

An illustrative P0 frame is:

```json
{
  "event_id": "9a797ac9-66a4-4ec5-ae66-c3af9f37aa13",
  "event_type": "metis.telemetry.frame.v1",
  "schema_version": 1,
  "source_id": "simulator/local-demo",
  "stream_id": "3edf94bf-a02c-4ef0-8f84-eb04fd1cd3a4",
  "satellite_id": "METIS-001",
  "sequence": 4182,
  "observed_at": "2026-09-21T08:09:42.000Z",
  "origin": "simulated",
  "producer": {
    "name": "metis-simulator",
    "version": "0.1.0",
    "model_version": "power-v1"
  },
  "data": {
    "catalog_version": "telemetry-catalog/1",
    "values": {
      "environment.eclipse": false,
      "operation.mode": "PAYLOAD_ACTIVE",
      "eps.solar.generated_power": 112.8,
      "eps.load.requested_power": 84.0,
      "eps.load.supplied_power": 84.0,
      "eps.battery.energy": 503.4,
      "eps.battery.soc": 0.763
    },
    "quality": {},
    "position": {
      "teme": {
        "position_km": [-4912.1, 284.2, 4820.7],
        "velocity_km_s": [-3.25, -6.41, -2.89]
      },
      "wgs84": {
        "latitude_deg": 32.1,
        "longitude_deg": 48.2,
        "height_m": 552000.0
      }
    }
  }
}
```

SGP4 produces TEME position/velocity; Astropy documents the output in km and km/s and shows the time-dependent conversion to ITRS/geodetic longitude, latitude, and height ([Astropy Earth-satellite coordinates](https://docs.astropy.org/en/stable/coordinates/satellites.html)). Preserve the coordinate frame and units in field names/schema. Generic `x`, `y`, `z`, `latitude`, or `altitude` without frame, datum, and unit are invalid contract fields.

### 4.2 Units, time, and metric catalog

Every numeric key has exactly one canonical meaning, type, and unit in an immutable metric catalog version. Use UCUM codes for machine-readable units; UCUM is intended to encode units used in science and engineering ([UCUM specification](https://ucum.org/ucum)). Recommended canonical examples are:

| Quantity | Unit/representation |
|---|---|
| battery SOC, eclipse fraction | `1`, bounded 0–1 |
| energy | `W.h` |
| power | `W` |
| voltage/current | `V`, `A` |
| temperature | `K`; convert for display |
| angles/angular rates | `rad`, `rad/s` |
| TEME position/velocity | `km`, `km/s` to match SGP4 output |
| WGS84 display height | `m` |

Never reuse a metric key with another unit, type, frame, sign convention, or physical meaning. Create a new key and catalog version instead. Display preferences such as percent, Celsius, or kilometers are UI conversions.

`observed_at` must include `Z` and represent UTC. Keep the numerical integration step and emitted sample index in the frozen stream manifest; do not derive ordering from floating-point timestamps. Astronomy libraries distinguish representation from time scale and require explicit scales for transformations ([Astropy time](https://docs.astropy.org/en/latest/time/)).

All numeric JSON values must be finite. PostgreSQL `jsonb` rejects `NaN` and infinity, and portable JSON consumers cannot rely on them ([PostgreSQL JSON primitive mapping](https://www.postgresql.org/docs/current/datatype-json.html)). For unavailable or invalid telemetry:

- omit an unsampled/not-applicable metric;
- set a sampled but invalid metric to `null` and add `quality[key] = "invalid"`;
- use quality values from a closed vocabulary such as `stale`, `estimated`, `invalid`, or `out_of_range`;
- never encode missing numbers as zero.

For real inputs, provenance may also include `source_observed_at`, `receiver_id`, `adapter_version`, and `clock_uncertainty_ms`. A receiver-estimated timestamp must say so; it must not masquerade as spacecraft event time.

### 4.3 Operational events

Mode changes, configured limit crossings, source resets, and data gaps use the same envelope with a different registered `event_type`. They consume sequence numbers from the same per-satellite stream, so a consumer can establish producer order across frames and operational events. Do not emit analytics conclusions such as anomaly, health score, fault probability, or predicted failure from this service.

Private fault activation is not an operational event. Only an effect observable to the spacecraft/operator, such as a measured energy-limit crossing, may appear in the public log.

## 5. Logical PostgreSQL model

Use three database schemas with separate roles:

```text
control    configuration revisions, public run manifests, lifecycle events
telemetry  source-neutral immutable event log, catalogs, optional consumer state
truth      private scenarios, latent fault state, evaluation outcomes
```

Minimum logical tables:

| Table | Essential columns/constraints |
|---|---|
| `control.config_revision` | `revision_id`, canonical resolved JSON, SHA-256 hash, created time; immutable. |
| `control.run` | `run_id`, `stream_id`, public revision, seed, epoch, cadence, speed, status, optimistic version, timestamps. |
| `control.run_transition` | append-only command/transition record, command ID, from/to state, sim/wall time. |
| `telemetry.metric_catalog` | immutable catalog version and JSON Schema/metadata. |
| `telemetry.event_log` | database `log_offset`, envelope columns, `data jsonb`, `content_hash`, `ingested_at`. |
| `telemetry.consumer_checkpoint` | optional named internal relay/projection cursor; not required for external readers. |
| `truth.run_manifest` | private fault schedule/config hash mapped to `run_id`; evaluator/simulator roles only. |
| `truth.event` | fault instance, satellite, latent-state transition, severity, actual onset/outcome time, evidence references. |

Essential event-log constraints and indexes:

```text
PRIMARY KEY (log_offset)
UNIQUE (source_id, event_id)
UNIQUE (source_id, stream_id, satellite_id, sequence)
INDEX  (source_id, stream_id, satellite_id, observed_at)
INDEX  (event_type, ingested_at)
CHECK  (sequence >= 0)
```

The application must compare `content_hash` when either unique identity already exists:

- same identity and same canonical content: successful duplicate retry;
- same identity and different content: `409 identity_collision`, never silently overwrite;
- new `event_id` but reused stream sequence: `409 sequence_collision`.

Compute the hash from a documented canonical serialization of the producer-supplied envelope, excluding database-added `log_offset` and `ingested_at`. A hash is an efficient comparison aid, not the event identity.

This is append-only. Corrections are new events referring to the superseded `event_id`; there is no update-in-place API for telemetry.

## 6. Ingestion and replay API semantics

### 6.1 In-process P0 writer

The simulator calls an application interface such as `append_batch(events)`. Its PostgreSQL implementation validates the complete batch and commits it atomically. Success means the transaction committed, not merely that an in-memory queue accepted work.

Use the same Pydantic `EventBatch` and `SourceEvent` models for a future `POST /v1/events:batch`. This avoids an internal HTTP hop in the one-process P0 while preserving an implementation-ready external boundary.

Suggested batch behavior:

- one batch contains 1–500 events and has a stable `batch_id` for request tracing;
- validation is all-or-nothing;
- exact duplicates are reported in `duplicate_count` and are not new rows;
- a collision rejects the batch with machine-readable offending identities;
- `201 Created` follows commit and returns `accepted_count`, `duplicate_count`, and the highest `log_offset`;
- after a timeout or connection loss, the producer retries the same event IDs and sequences with exponential backoff and jitter.

Do not promise exactly-once delivery. The boundary is at-least-once retry plus idempotent effects. MQTT itself distinguishes at-most-once, at-least-once with possible duplicates, and protocol-level exactly-once with greater exchange overhead ([MQTT 5.0 QoS](https://docs.oasis-open.org/mqtt/mqtt/v5.0/mqtt-v5.0.html)). Application identity and database constraints remain necessary even if a future transport advertises stronger QoS.

### 6.2 Pull/replay

Expose a source-neutral read such as:

```text
GET /v1/events?after=<opaque-cursor>&limit=500
    [&source_id=...][&stream_id=...][&satellite_id=...][&event_type=...]
```

Response fields are `items`, `next_cursor`, and `has_more`. The cursor is opaque, versioned, and advances by committed `log_offset`; consumers must not construct or decrement it. A consumer persists its cursor only after its durable side effect completes.

Why the cursor is not `sequence` or `observed_at`:

- sequence ordering is scoped per satellite, not global;
- different sources and satellites interleave;
- a future adapter may deliver a late observation;
- equal timestamps are valid;
- simulation time may jump between streams.

The API is at-least-once across a consumer crash. The consumer deduplicates on `(source_id, event_id)` and can use per-stream sequence to identify gaps or reordering. A gap is metadata, not proof of data loss: it may reflect a filtered event type or an upstream source omission.

### 6.3 WebSocket projection

The WebSocket is a viewer optimization, never the durable producer contract. It emits at most the configured wall-clock presentation rate, carries the latest committed frame per satellite, and includes the last persisted `event_id`, `sequence`, and `observed_at` so the UI can show freshness. Slow clients receive a coalesced newer snapshot and may miss intermediate frames. Reconnect loads a snapshot and continues; it does not replay history.

This cleanly supports 20x simulation: the log keeps all 1 Hz simulated frames while the globe can update at 2–5 wall-clock Hz.

## 7. Backpressure and failure behavior

Use separate policies for durable data and presentation:

| Path | Policy when slow |
|---|---|
| Simulator to event log | Bounded queue; block/pause simulation-clock advancement before dropping a committed-required frame. |
| Log to internal projector | Resume from durable cursor; retries are idempotent. |
| Projector to WebSocket | Coalesce by satellite; disconnect persistently slow clients. |
| Future outbound relay | Retry with backoff; retain relay cursor/outbox state; downstream deduplicates. |

Reasonable load-test starting values, not performance guarantees:

- flush at 200 events or 250 ms, whichever comes first;
- maximum batch 500 events;
- bounded pending queue 2,000 events, which represents 10 seconds at the 200-frame/s P0 maximum;
- expose queue depth, oldest queued age, batch commit latency, accepted/duplicate/collision counts, and paused-for-backpressure state.

When the queue reaches its limit, pause paced simulation and surface a health error. Do not keep advancing the canonical clock and silently discard frames. A manual stop must first define whether queued frames drain or the run becomes failed; the recommended P0 behavior is a bounded drain followed by `FAILED` if durability cannot be confirmed.

## 8. Run lifecycle and reproducibility

Recommended lifecycle:

```text
CREATED -> RUNNING <-> PAUSED -> COMPLETED
                   \          -> STOPPED
                    ----------> FAILED
```

- `COMPLETED` means the configured end condition was reached.
- `STOPPED` is an operator-requested terminal state.
- `FAILED` means execution or required persistence failed.
- Reset creates a new run and stream; it never erases or rewinds an old log.
- Speed changes are allowed in `RUNNING` or `PAUSED` and are appended as control transitions. `0x` is invalid; use pause.
- Commands carry a command ID for idempotency and use compare-and-set on the run's optimistic version.
- Pausing freezes simulation time after the last committed step.

On create, resolve YAML references/defaults into canonical JSON and freeze:

- public satellite/constellation configuration revision and hash;
- satellite membership and stable IDs;
- simulation UTC epoch, duration/end condition, integration step, telemetry cadence;
- random seed and per-satellite derived seeds;
- model names/versions and producer build identifier;
- initial state and source/stream IDs;
- private scenario revision and hash in the truth schema.

YAML is an authoring format, not the persistence contract. An edit or newly added satellite creates a new configuration revision and affects only new runs. Active-run membership and physics parameters do not mutate.

P0 need not support mid-run process recovery. After an uncheckpointed process crash, mark the run `FAILED`; regenerate deterministically as a new run/stream from the manifest. Claiming resume requires persisted state checkpoints that include integrator, random-generator, subsystem, schedule, and next-sequence state.

## 9. Hidden truth and access separation

Truth must be structurally difficult to leak, not merely named with an underscore.

- The analytics/Grafana role receives `USAGE`/`SELECT` only on approved `telemetry` views and public `control` views. It has no grant on `truth`.
- The public run manifest contains the fact that a run is synthetic and its public reproducibility data, but no fault type, onset, latent derating, threshold-crossing future, or private seed derivation.
- Private scenarios and truth events use separate models and routes; no public response model contains optional truth fields.
- General logs, metrics labels, error payloads, WebSocket messages, and OpenAPI examples must not serialize private scenario objects.
- Evaluation uses an explicit evaluator credential and joins truth after analytics output exists.
- Healthy controls have explicit truth status such as `no_injected_fault`, rather than an ambiguous missing row.

PostgreSQL supports table-specific row security, but superusers and roles with `BYPASSRLS` bypass it ([PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)). For P0, separate schemas plus explicit least-privilege grants are easier to audit. RLS can supplement those grants; it should not be the only protection while the application connects as an owning/bypass role.

Truth should distinguish:

1. scenario scheduled;
2. latent degradation activated;
3. latent severity progression;
4. an observable operational criterion crossed;
5. terminal failure outcome, if any.

This permits detection latency and prediction lead-time evaluation without leaking the answer into public telemetry. The public limit-crossing event may be visible at step 4; steps 1–3 remain private.

## 10. Broker and outbound transport decision

### P0: no broker

A broker adds deployment, retention, consumer, and failure semantics while PostgreSQL already provides the required durable replay. The simulator and API are one process and one writer; an internal interface is sufficient.

### Future HTTP push

If Metis later needs to push committed events to another service, tail the log with a durable relay checkpoint or create `delivery_outbox` references in the same transaction as the frame append. The relay sends batches with stable event IDs; a crash after remote acceptance but before checkpoint update causes a safe duplicate retry.

The transactional outbox pattern exists to avoid a database/message dual write: the record and outbox are committed together, while consumers still need idempotency because relays can publish duplicates ([AWS transactional outbox guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)). Since this design's immutable event log is already the committed payload, it can serve as the relay source; a separate outbox table is needed only for destination-specific state, transformations, or selective delivery.

### Future NATS JetStream

Choose NATS JetStream if independent durable subscribers, subject routing, or cross-process fan-out becomes a measured need. JetStream supports replay and at-least-once consumers; `MaxAckPending` bounds unacknowledged delivery, and message IDs provide deduplication within a configured window ([NATS consumers](https://github.com/nats-io/nats.docs/blob/master/nats-concepts/jetstream/consumers.md), [NATS JetStream headers](https://github.com/nats-io/nats.docs/blob/master/nats-concepts/jetstream/headers.md)). Map `event_id` to `Nats-Msg-Id`, but retain database idempotency because broker deduplication windows and application side effects are different concerns.

### Future MQTT

Choose MQTT when constrained or intermittently connected devices/edge gateways are actual producers and topic/QoS interoperability is required. It is not useful merely because the payload is called telemetry. An MQTT adapter maps topics and QoS deliveries into the same event envelope and creates a new `stream_id` when a device's sequence epoch resets.

## 11. Schema evolution rules

Keep wire schema, metric catalog, and database schema versions separate.

1. `schema_version` changes only for a breaking envelope or event-data change.
2. Within v1, producers may add optional fields; consumers must ignore unknown fields.
3. A required-field removal, rename, type change, or semantic change creates v2 and a new `event_type` suffix.
4. A metric addition creates a new immutable `catalog_version`; old streams retain their pinned catalog.
5. A unit, coordinate frame, sign convention, or meaning change creates a new metric key. Never reinterpret historical values.
6. The service publishes generated JSON Schemas and representative fixtures for each supported event/catalog version.
7. Store raw accepted v1 data unchanged. Migration views/adapters may expose newer shapes; do not mutate historical payloads in place.
8. Support at least the current and previous major reader during migration; reject an unsupported producer version before any rows commit.

Contract tests should validate Pydantic models against published JSON examples and verify that unknown additive fields do not break the supported consumer adapter.

## 12. Reviewable edge cases and acceptance probes

| Edge case | Required result |
|---|---|
| Producer times out after database commit and retries the batch | No new rows; duplicate count returned; identical cursor result. |
| Same `event_id` is retried with changed payload | Whole batch rejected with `identity_collision`. |
| Same stream sequence is reused with another event ID | Whole batch rejected with `sequence_collision`. |
| Sequences arrive `10, 12, 11` from a future adapter | All unique events can be appended; log cursor sees commit order; sequence-aware consumer reports/reorders the gap. P0 simulator itself must emit monotonically. |
| Two satellites emit sequence `42` | Both accepted because sequence scope includes satellite ID. |
| Source process restarts and would reset sequence | It must create a new `stream_id`; reusing the stream is rejected on collision. |
| Two values share a timestamp | Both accepted if event identities/sequences differ; timestamp is not identity. |
| Numeric value is `NaN`/infinite | Validation rejects before insert. |
| Satellite has no position from a real source | Optional `position` omitted; telemetry remains valid. |
| Metric is unavailable vs measured zero | Unavailable is absent/null plus quality; zero remains numeric zero. |
| Run is paused during an eclipse boundary | Last step commits, time freezes, resume continues from the next deterministic step. |
| Speed changes at a tick boundary | Transition is recorded; simulated cadence remains 1 Hz and only wall pacing changes. |
| User edits YAML or adds a satellite during a run | New revision only; active run and stream remain unchanged. |
| WebSocket client cannot keep up at 20x | Intermediate presentation updates coalesce; every durable frame remains queryable. |
| HTTP replay consumer crashes after side effect but before cursor save | Event redelivers; consumer event-ID dedupe prevents duplicate effect. |
| Simulation is regenerated from the same frozen configuration, seed, and model version | Values and event ordering match except explicitly excluded wall/ingest metadata and newly assigned run/stream/event IDs. |
| Analytics role attempts to select private truth | Database permission denied; no API or schema discovery path returns truth. |
| Private fault is scheduled but has no observable effect yet | Public telemetry contains only physical effects; no label or upcoming-fault hint. |
| Database remains unavailable beyond the bounded queue | Simulation clock pauses and run health reports backpressure; it does not silently drop data. |
| Process crashes without a state checkpoint | Run becomes `FAILED`; deterministic regeneration uses a new run/stream. |
| Old v1 consumer receives an additive optional field | It continues after ignoring the unknown field. |
| A metric's unit must change | New metric key/catalog version; old history remains interpretable. |

## 13. Conflict points resolved for the specification

1. **`replay` provenance:** replay is delivery context, not origin. Preserve `simulated` or `observed`; use `derived_from` only when creating a new transformed stream.
2. **Partitioning:** do not partition on day one. If retention later requires it, partition by ingest time rather than accelerated simulation time.
3. **Truth in run configuration:** store public and private manifests separately. A single config blob with API-level field filtering is too easy to leak.
4. **Server-managed consumer offsets:** external consumers own their cursor in P0. Server-side checkpoints are reserved for named internal projectors/relays.
5. **Broker guarantees:** use at-least-once plus stable IDs and idempotent effects. Do not make an end-to-end exactly-once claim.
6. **Wide versus narrow telemetry:** one row per satellite tick is the P0 source of truth. Future analytical stores may normalize or columnize it downstream.
7. **Run identity in analytics:** control metadata maps a run to a stream, but analytics ingests `source_id`, `stream_id`, `satellite_id`, and `sequence`; it does not require a simulation run concept.

## 14. Implementation order

1. Define strict current-producer Pydantic models for frozen public/private manifests, source events, batches, cursors, and metric catalog; generate schemas and fixtures. Keep supported consumer adapters tolerant of unknown optional fields.
2. Create the three PostgreSQL schemas, least-privilege roles, immutable tables, identity constraints, and atomic append function/repository.
3. Implement the in-process producer boundary and deterministic run lifecycle with one writer.
4. Implement cursor reads and prove retry/collision/reconnect behavior before the WebSocket.
5. Implement a latest-state projector and coalescing WebSocket from committed frames.
6. Add truth evaluation paths using an explicit evaluator role and automated leakage tests.
7. Run the 3-satellite/20x and 10-satellite/20x load tests and record the hardware and measurements before changing storage technology.
