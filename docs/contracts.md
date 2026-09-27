---
title: Configuration and Data Contracts
description: Specify satellite configuration, public measurements, private truth, persistence, and transport behavior.
content-type: reference
audience: engineering
status: normative implementation contract
version: 1.0
date: 2026-09-21
---

# Configuration and Data Contracts

This is a normative appendix to the [specification](specification.md).
The endpoint paths and schemas below define the implemented contract for this version. The [API consumer guide](api.md) shows how to use the running service.

## 1. Objects and Responsibility

| Object | Identity and lifetime | Owns | Must not own |
|---|---|---|---|
| `SpacecraftProfile` | Named entry in a configuration revision | Supported subsystem types, panel geometry, battery parameters, load table, sensor definitions | Mutable runtime state or a fault schedule |
| `SatelliteDefinition` | Stable `satellite_id` plus configuration revision | Profile reference, orbit initialization, name, optional visual asset reference | Network delivery or global simulation time |
| `ConstellationDefinition` | ID plus a set of satellite IDs | Membership and display grouping | Implicit links, force interactions, or shared subsystem instances |
| `RunManifest` | New UUID for every execution | Resolved private configuration, seed, epoch, duration, model/data versions and hashes | Public analytics access to private scenario parameters |
| `SimulationClock` | One per active run | Integer tick, elapsed duration, epoch, speed target, pause state | Browser clock or an independently ticking clock per satellite |
| `SatelliteState` | One per satellite per run | Current physical state, battery energy, operating mode, fault modifier state | HTTP clients or database sessions |
| `OrbitState` | Satellite and simulation instant | Position, velocity, explicit frame and epoch | UI interpolation or subsystem fault outcomes |
| `EnvironmentState` | Satellite and simulation instant | Sun direction/distance, shadow fraction, panel incidence | Independent random power generation |
| `MeasurementFrame` | Source, stream, sequence | Allowlisted measured/derived public channels and quality | Fault labels or future outcomes |
| `OperationalEvent` | Source, stream, event sequence | Observable mode transitions and limit crossings | Hidden injection start events |
| `TruthRecord` | Run, satellite, private sequence | Injected cause, severity trajectory, observed outcome and censoring | Delivery through ordinary consumer routes |
| `VisualAsset` | Optional catalog ID | Allowlisted local GLB URI, scale, orientation correction, checksum | Physics parameters or UI code to run |

Use composition: a profile chooses supported models by discriminated `type` fields.
Do not create a new Python subclass for every named satellite.
A registry maps a small set of supported model names to constructors; it is internal code, not a plugin marketplace or dynamic Python import path from YAML.
Adding a satellite with existing model types requires configuration only.
Adding new physics requires a new model implementation, schema version/catalog update as appropriate, and contract tests.

P0 model boundary operations are `initialize(config, context)`, `advance(state, inputs, dt)`, and `measure(state, sensor_context)`.
They return new state or mutate exclusively owned state; this choice must be consistent within the domain package.
Only the runner coordinates the order of models.
Models do not query one another through services.
Shared inputs are immutable, and the load aggregation/power balance has exactly one owner.
All Python public classes and functions must use NumPy-style docstrings.

## 2. Configuration Rules

**CFG-03:** YAML and API JSON must enter the same Pydantic validation and normalization path.
Generate JSON Schema and Dart contract types from those models; do not maintain separately handwritten competing schemas.
Pydantic supports JSON Schema generation from models. [Pydantic documentation](https://docs.pydantic.dev/latest/concepts/json_schema/)

Required root sections are `schema_version`, `run`, `profiles`, `satellites`, `constellations`, and `scenario`.
`scenario` is private, including when its value is an empty list.
Unknown keys, unknown types, non-finite floats, duplicate IDs, unresolved references, unsafe YAML tags, and timestamps without UTC offsets must fail validation.
Use a safe YAML loader, reject duplicate mapping keys, disable user-defined tags, bound file size to 1 MiB, and limit satellites to 10 for P0.
Reject aliases that exceed bounded nesting/expansion; no executable expressions, arbitrary URLs, or environment-variable expansion are permitted in submitted physics configuration.

The schema must validate positive capacity/area, efficiency in `(0,1]`, SOC and illumination in `[0,1]`, supported orbital envelope, an existing profile for every satellite, monotonically ordered fault control points, schedule intervals within the run, and unique membership IDs.
An operation has integer `start_s` and `end_s` and a mode; its optional `repeat` accepts `orbit` or `null`/omission, with null/omission meaning one-time.
For `orbit`, derive the fixed recurrence period from the satellite's initial `a_m` as `2*pi*sqrt(a_m**3/MU)`, with `MU=3.986004418e14 m^3/s^2`.
Starts are `start_s + round(n*T)` for `n=0,1,...`, using Python nearest-integer ties-to-even rounding, and each end is its start plus the declared interval duration.
Cadence is anchored to the first operation and is not adjusted for J2 crossings or phase.
Require the first declared interval to fit the run; consider later windows whose starts are at or before run end, integrate only to run duration, and retain active terminal mode if the last window extends past it.
Reject overlaps among declared and generated intervals, and restore `initial_mode` outside operation windows.
A run allows at most one `solar_derating` scenario per satellite.
An operation may also carry `added_load_w` (0 to 10,000 W, default 0), added to its mode's load while active, and an optional public `label` with the identifier grammar.
An optional `min_start_soc` (0 to 1) is an onboard start guard: when the battery state of charge at the window's start tick is below it, the spacecraft skips the whole window, staying in `initial_mode` with no added load, and emits `operation_skipped`. The guard is checked only at the start and never ends a running window.
All per-satellite operational schedule overlaps, including safe-mode overlaps, are rejected in P0.

The fixed P0 validation matrix is:

| Field | Accepted values |
|---|---|
| `run.tick_s`, `run.telemetry_period_s` | Both exactly 1. |
| `run.duration_s` | Integer 1–86,400; default 21,600. |
| `run.speed` | Positive whole-number multiplier; default 90. |
| `run.seed` | Integer 0 through `2^53-1`; required. |
| `run.earth_model` / `orbit_model` / `sun_model` | `wgs84_j2_v1` / `j2_cartesian` / `astropy_builtin`. |
| `run.environment_source` | Optional public name (1–160 characters) of recorded data that shaped the simulated environment; copied to `PublicRunStatus.environment_source`. It names a source, never scenario values. |
| `panel.pointing.type` / `battery.type` | `ideal_sun_tracking` / `energy_store`. |
| `sensors.noise.type` | `none` in the baseline; optional seeded noise requires a separately specified supported model. |
| `initial_mode`, operation `mode` | `nominal`, `payload_active`, `safe`. |
| operation `repeat` | Omitted or `null` for one-time; `orbit` for fixed nominal two-body recurrence. |
| `scenario[].type` / `outcome.type` | `solar_derating` / `energy_reserve_violation`; empty scenario list allowed. |
| Outcome | `reserve_soc` strictly between 0 and 1; `dwell_s` positive integer; baseline dwell 60. |

Normalization resolves each profile reference into a complete immutable satellite definition, materializes defaults, sorts keyed collections, converts times to UTC, and hashes canonical JSON with SHA-256.
Arrays whose order is meaningful retain order.
Canonical bytes use RFC 8785 JSON Canonicalization Scheme, UTF-8, after schema normalization; preserve Unicode strings as specified by that standard and represent all numbers in its supported interoperable range.
Use those same rules for request hashes and identity/payload collision checks; JSON duplicate keys and non-finite numbers are rejected before canonicalization.
The canonicalization algorithm and schema version must be recorded so hashes are repeatable. [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785)
IDs use ASCII `[A-Za-z0-9_-]{1,64}` and are case-sensitive.

Create/edit operations produce a new revision.
No active run can change its profile, orbital initial state, seed, fault schedule, or membership.
Changing speed/pause affects wall-clock pacing only.
Adding a satellite from a future dashboard means submitting the same schema and creating a subsequent run; hot insertion and mid-run configuration migration are outside P0.
Deleting a catalog entry cannot invalidate an existing run's resolved snapshot.

## 3. Public Measurement Envelope

**DATA-03:** The producer-neutral event identity is `(source_id, stream_id, sequence)`.
`source_id` is a registered producer identity; `stream_id` is a UUID representing one monotonically sequenced series for one satellite.
Each new simulation run allocates new streams, including after reset or regeneration.
A real-source adapter also allocates a new stream on counter reset rather than reuse old identities.
Sequences start at zero and increase by one per generated frame; a skipped/dropped frame is detectable as a sequence gap.
P0 simulation commits all generated frames or pauses/fails rather than silently dropping them.

The `satellitecots.v1` adapter reads the immutable BUPT-1 source corpus from
Postgres and allocates a new run and stream for every playback or source-time
seek. Its dense `sequence` counts delivered source records; `committed_tick`
tracks elapsed source seconds and `committed_sequence` tracks the last durable
record. These values differ after a seek or a recorded gap. Original source
timestamps and missing intervals are preserved. `mode` and `interval_mode` are
null because this source does not identify spacecraft operating mode.
Its channel catalog declares endpoint semantics, with `sample_window_s=0`;
unit-converted sensors and explicit electrical derivations are never presented
as interval averages. See [source inventory](research/satellitecots.md).

`GET /v1/datasets` exposes installed dataset metadata without future channel
values. `POST /v1/viewer/source` selects `physics` or `satellitecots` for a new
unstarted run; `POST /v1/viewer/seek` accepts an original-source `elapsed_s` and
prepares a new recorded stream at the next available sample. A seek validates
its position before stopping the current replay. Start is explicit afterward.
Both viewer mutations retain session authorization, CSRF and idempotency rules.
Reset preserves the selected source and returns recorded playback to zero.
Unsupported observed nameplate values are null; no modelled orbital channel is
added to the observed measurement stream. The existing trajectory endpoint can
return a separate `kind=configured_orbit` presentation with an explicit
`description`. It uses a run-snapshotted BUPT-1 orbit configuration based on the
operator's public altitude and inclination, with disclosed phase/orientation
assumptions. Its UTC positions follow the same replay clock. The existing viewer
configuration endpoint permits orbit-only edits while retaining the single
recorded spacecraft, source metadata and measurements. Reset and seek preserve
those orbital settings; switching to physics preserves its separate constellation.

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | string | `telemetry.v1`; breaking changes create a new major schema. |
| `source_id` | string | Producer identity, e.g. `metis-simulator-local`. |
| `stream_id` | UUID | One satellite's series within a run/session. |
| `sequence` | nonnegative integer | Per-stream order; JSON clients must reject values beyond their exact integer range. |
| `satellite_id` | string | Logical spacecraft identity; stream metadata binds it to the producer. |
| `source_kind` | enum | `synthetic` or `observed`; replay does not change provenance. |
| `time_domain` | enum | `simulation_utc` or `mission_utc`. |
| `observed_at` | UTC RFC 3339 string | Time represented by the values, never HTTP receipt time. |
| `sample_window_s` | nonnegative finite number | Interval length ending at `observed_at` for interval-average channels; 0 for the initial instantaneous frame, 1 for subsequent P0 frames. Other producers may use another declared window. |
| `emitted_at` | UTC RFC 3339 string | Wall time the producer serialized the event; preserved on retry. |
| `catalog_version` | string | Immutable public channel catalog identity. |
| `mode` | enum | P0 `nominal`, `payload_active`, or `safe`; unknown future modes are displayed as unknown by old consumers. |
| `interval_mode` | enum or null | Mode used for interval-average powers. Equals `mode` at sequence zero; may differ at an endpoint transition. Null for producers whose mode over the window is unknown, without inferring it from endpoint mode. |
| `channels` | object | Channel ID → `{value, quality}`. Value is a finite scalar, fixed-length finite vector, enum, or null as declared in the catalog. |

The ordinary ingestion service adds its own `received_at` wall time without overwriting event fields.
Frame `sequence` and `event_sequence` must be integers in `[0,9007199254740991]` (`2^53-1`); allocate a new stream before rollover.
`run_id`, seed, fault configuration, and simulator progress are not required fields for a real producer.
The simulator's public stream descriptor may link its stream to a run for UI discovery; analytics must not require that link.

Quality enum: `valid`, `missing`, `invalid`, `saturated`.
The catalog declares sensor resolution, unit, scalar/vector type, coordinate frame where applicable, nominal cadence, `origin` (`sensor` or `derived`), `sampling_semantics` (`endpoint` or `interval_mean`), and description.
All P0 `*_w` power channels have `interval_mean` semantics over `(observed_at-sample_window_s, observed_at]`; all other channels and top-level `mode` have `endpoint` semantics.
The sequence-zero frame uses `sample_window_s=0` and instantaneous allocation for power, as explicitly defined in the physics appendix.
Missing readings are null with `missing`; invalid sensor readings are null with `invalid`; saturation preserves the boundary value with `saturated`.
Absent channels mean unsupported by that profile; a supported channel with a failed sample remains present with null/quality.
There are no NaN/Infinity JSON values or magic numeric missing-value codes.
Synthetic provenance is attached to the source, not used as an excuse to call hidden simulator state a measured channel.

Normative P0 channel catalog:

| Channel | Unit / type | Origin and meaning |
|---|---|---|
| `orbit.position_itrf_m` | m / vector[3] | Derived Cartesian Earth-fixed position at `observed_at`. |
| `orbit.velocity_itrf_m_s` | m/s / vector[3] | Derived time derivative in the same rotating frame, including frame-rotation effects. |
| `orbit.latitude_deg` | deg / scalar | Derived WGS84 geodetic latitude. |
| `orbit.longitude_deg` | deg / scalar | Derived east-positive longitude in `[-180,180)`. |
| `orbit.altitude_m` | m / scalar | Derived WGS84 ellipsoidal height, not terrain or spherical radial altitude. |
| `environment.illumination_fraction` | 1 / scalar | Derived fraction of the solar disk visible to the satellite. |
| `environment.panel_incidence_cosine` | 1 / scalar | Derived sunward cosine for the P0 single equivalent panel. |
| `eps.solar_power_w` | W / scalar | Synthetic sensor for generation delivered to the bus. |
| `eps.load_requested_w` | W / scalar | Derived sum of requested loads for active mode. |
| `eps.load_served_w` | W / scalar | Synthetic sensor for load actually supplied. |
| `eps.battery_power_w` | W / scalar | Synthetic sensor; positive when discharging into the bus, negative when charging from it. |
| `eps.battery_energy_wh` | Wh / scalar | Derived ideal onboard energy estimate in P0; catalog discloses that it is idealized. |
| `eps.battery_soc` | 1 / scalar | Derived energy divided by configured fixed usable capacity, in `[0,1]`. |
| `eps.curtailed_power_w` | W / scalar | Derived generation not used by loads or battery charging. |
| `eps.unserved_power_w` | W / scalar | Derived unmet requested load. |

Public nameplate parameters such as nominal capacity and installed panel area may be provided in an allowlisted spacecraft descriptor.
Hidden fault multipliers, failure thresholds used only for evaluation, upcoming fault timing, and future physical state are not part of that descriptor.
P0 sensor noise is zero by default for exact verification; optional seeded noise and quantization apply only after solving physics.
Do not feed noisy readings back into the physical energy balance.

Example event fragment; a full frame contains all supported catalog channels.
These protocol-only values illustrate a 400 Wh battery at SOC 0.7 and a 150 W nominal load; they are not a calculated sample from the example orbit/run history.

```json
{
  "schema_version": "telemetry.v1",
  "source_id": "metis-simulator-local",
  "stream_id": "8152b6ac-8f6c-4d54-94eb-764b414a1b9c",
  "sequence": 60,
  "satellite_id": "METIS-01",
  "source_kind": "synthetic",
  "time_domain": "simulation_utc",
  "observed_at": "2026-09-21T00:01:00Z",
  "sample_window_s": 1,
  "emitted_at": "2026-09-21T08:00:03Z",
  "catalog_version": "power-leo.v1",
  "mode": "nominal",
  "interval_mode": "nominal",
  "channels": {
    "eps.solar_power_w": {"value": 200.0, "quality": "valid"},
    "eps.load_requested_w": {"value": 150.0, "quality": "valid"},
    "eps.load_served_w": {"value": 150.0, "quality": "valid"},
    "eps.battery_power_w": {"value": -50.0, "quality": "valid"},
    "eps.battery_energy_wh": {"value": 280.0, "quality": "valid"},
    "eps.battery_soc": {"value": 0.7, "quality": "valid"},
    "eps.curtailed_power_w": {"value": 0.0, "quality": "valid"},
    "eps.unserved_power_w": {"value": 0.0, "quality": "valid"}
  }
}
```

## 4. Truth and Operational Events

**FLT-02:** Fault schedules change physical model parameters before state advancement; they do not overwrite final telemetry fields.
A sensor fault, if added later, changes the sensor model explicitly and is distinguished from a physical fault.
The authoritative tick order is the interval/endpoint sequence defined in the physics appendix: interval-start operations and midpoint fault modifier → physical integration → endpoint operations/outcomes → measurement of endpoint state plus the completed interval's powers → atomic persistence.
Do not apply an endpoint mode change retroactively to the interval just completed.

Private truth includes `run_id`, `satellite_id`, fault instance/type, injection onset, current hidden multiplier, first observable symptom if defined, outcome rule/version, actual failure time if reached, and run-end censoring.
Outcome time is null until the rule actually triggers; a configured future timestamp is never an actual failure label.
An unfinished or healthy run must be marked right-censored at its last valid simulation time, with reason (`duration_reached`, `stopped`, `failed`, or `aborted`).
Do not label a healthy run as “failure at end of file.”

Operational events use the associated telemetry `stream_id` with a separate `event_sequence` starting at zero, not the frame `sequence`.
Their identity is `(source_id, stream_id, event_sequence)` within the event table/type; event cursors are explicitly bound to this sequence namespace.
The required envelope is `{schema_version: operational_event.v1, source_id, stream_id, event_sequence, satellite_id, source_kind, time_domain, observed_at, emitted_at, event_type, reason_code, details}`.
`details` is an allowlisted payload defined per event type; unknown arbitrary domain fields must not be serialized.
P0 events include `mode_changed`, `low_energy_limit_entered`, `low_energy_limit_cleared`, `power_unserved`, and `operation_skipped`.
Public limit events describe an existing measured condition and may be used for detection workflows; they are not future-failure ground truth.
The optional profile field `public_limits` defaults to an empty list; each configured entry has `channel_id`, `operator` (`lt` or `gt`), `value`, and `clear_value` for hysteresis.
P0 only supports limits on `eps.battery_soc`; require clear_value ≥ value for `lt` and clear_value ≤ value for `gt`.
Emit entered/cleared once on transitions and expose these public limit definitions in the spacecraft descriptor.
The complete example deliberately has no public low-energy limit configured; its private reserve-outcome rule does not implicitly create a public limit event.
`mode_changed` comes from the public operating state.
`operation_skipped` (reason `battery_below_start_limit`) is emitted at the start tick of a guarded window the spacecraft skipped; its details are `{label, mode, start_s, end_s, battery_soc, min_start_soc}`, all public configuration or observed values.
`power_unserved` is emitted only when unserved power changes between zero and positive; its details are `{active, value_w, sample_window_s}` and contain only the observed value/window.
Clearing occurs exactly at zero; no private threshold is involved.
For public low-energy `lt` limits, entry is strictly below value and clear is greater than or equal to clear_value; reverse those comparisons for `gt`.
Private events such as `injection_started` must never appear there.

The default analytics token can read only allowlisted channel/spacecraft descriptors, public frames, and operational events.
The simulation operator token can manage runs and configurations.
The evaluation token can read truth and export labels; it is never shipped to the browser viewer or analytics client.
The operator configuring scenarios can of course know the fault; this is a controlled evaluation boundary, not a claim that the demo presenter is blinded.
The browser principal is a separate `viewer_control` role: its server-issued, expiring same-origin session binds one `run_id` and an explicit `allowed_actions` set, plus its public read routes.
Operator-issued sessions may use `start`, `pause`, `resume`, `set_speed`, and `stop` for that run. An explicitly enabled hosted public demo issues read-only sessions with no run actions; visitors can explore the globe and public telemetry while the server owns run lifecycle.
The existing control endpoint accepts either a broad operator principal or this exact run/action-scoped principal; other run IDs/actions return `403`.
Session issuance is handled by the deployment's authentication adapter during operator-authorized demo setup; it cannot mint broader permissions from browser-provided claims.
Define its verified internal claims as `{role, run_id, allowed_actions, expires_at, public_demo}` and enforce expiry server-side on HTTP requests and WebSocket reconnects; an active socket closes when its session expires. Disabling public demo issuance also invalidates outstanding public demo grants.
Use an HttpOnly, SameSite session cookie, Secure on HTTPS deployments, with Origin/CSRF checks on control requests. No new public account/registration API is needed for the prepared demo.
Acceptance fixtures issue this restricted principal through the auth adapter and prove control succeeds for its run but configuration/private routes and other runs remain forbidden.

### Mock Operator Sessions

The Flutter demo opens as `operator1` by default. Packaged `data/mock_operators.json` contains
fixed `user_id`, `login`, and `display_name` records for three demo operators.
The sidebar selects `operator1`, `operator2`, or `operator3`. Internally,
`POST /v1/viewer/login` accepts a listed login and any nonempty demo placeholder;
it performs no password verification and never stores the placeholder. Issuance is restricted to
the existing loopback demo boundary or an explicitly enabled interactive HTTPS demo.
Each login creates a separate run with a server-selected `private.runs.user_id`.
Editing or resetting copies this ownership into the replacement run transactionally.
Existing non-user runs retain a null `user_id`.

`ViewerBootstrap.operator` exposes the current demo profile only in the viewer
session response. The identity does not enter public telemetry or run-status payloads.
`GET /v1/viewer/session` restores a signed operator session and scoped run. It
returns `401` without one; the Flutter client then selects `operator1` through
the existing demo issuance route. This does not issue broader operator privileges.
`POST /v1/viewer/logout` requires the valid session's Origin and CSRF token, stops
only its active demo run, and deletes the cookie. The Flutter client clears old
samples and cancels streams before selecting another operator.
The private manifest records the signed session's expiry. A later login stops
expired operator-owned active runs before allocating a new run, so an abandoned
paused session cannot occupy the single-writer slot indefinitely.
Unexpired and legacy runs are not reclaimed by this operator cleanup.
These mock identities are not evidence of a verified person's identity and do not
grant bearer-operator or evaluator privileges.

Use separate SQL schemas/roles or equivalently restricted repository access, distinct response models, and negative access tests.
Do not merely remove `fault` from one JSON response while exposing it through the manifest, scenario name, logs, filesystem exports, or future orbit/health preview.

## 5. Run and Time Semantics

The complete run-state enum is `created`, `running`, `paused`, `completed`, `stopped`, `failed`, and `aborted`.
Transitions are `created → running ↔ paused`, `running → completed`, `running/paused → stopped`, and active execution → `failed` on a recorded unrecoverable error.
On recovery, a persisted `running/paused` run without a live owner transitions to `aborted`.
All response models, database checks, lifecycle messages, retention rules, and terminal-state tests use this same enum.
`completed` means configured duration was reached; stopping early is not successful completion.
Terminal runs are immutable and cannot restart; regeneration creates a new run and new streams.
Process restart marks any formerly running/paused run `aborted` (a terminal recovery state), preserves committed history, and requires explicit regeneration in P0.
Recovery does not guess lost in-memory battery state.
On completion/stop/failure/abort, finalize truth at the last committed sample: retain an already observed failure, otherwise mark the outcome right-censored with the terminal reason (`duration_reached`, `stopped`, `failed`, or `aborted`).
Commit terminal lifecycle and censoring together when the database is available.
If storage is unavailable, expose failure through process health, stop advancement, and reconcile a still-active persisted run as `aborted` with censoring on recovery; never pretend the terminal transaction was committed.

Reproducibility compares a canonical projection ordered by satellite ID and sequence: simulation timestamps/windows, modes, channel values/quality, public event type/reason/timing, and private physical/truth values.
Exclude run/stream/generated IDs and all wall-time metadata; preserve sequence because it is deterministic.
Use RFC 8785 canonical JSON for projection serialization and the numeric tolerances in physics gates P-08/P-10.
Derive independent random streams from SHA-256 of the documented tuple `(root_seed, satellite_id, sensor_channel_id)` using a named pinned NumPy generator; never Python's randomized `hash()` or one process-global generator.
Noise sampling consumes a fixed per-channel count per telemetry tick, even for null readings, so ordering, pausing, or adding another satellite cannot perturb existing streams.

P0 uses one active run and one writer process.
Multiple Uvicorn workers must not each run their own simulation loop.
Acquire a PostgreSQL advisory lock for the configured source identity for the writer's lifetime; a second instance fails readiness instead of creating a second loop.
Enforce at most one running/paused run per source in the transactional lifecycle repository.
The runner advances all satellites in stable ID order with independent state and deterministic seeds.
Use one integer simulation tick, fixed `dt=1 s`, samples at t=0 and each completed tick through the configured duration inclusive, and an epoch-to-time mapping defined in the physics appendix.
Duration must be an integer number of ticks.
Fault/schedule timestamps must align to a tick in P0; reject unaligned requests.

Requested speeds are `1`, `5`, and `20` simulated seconds per wall second.
Speed uses a monotonic wall clock only for pacing; simulation integrators always receive the fixed simulated `dt`.
Never enlarge the physical time step to catch up or skip telemetry to reach a requested speed.
If computation/storage is slow, report lower effective speed and increasing wall lag.
Pause takes effect at a committed tick boundary; it does not hold open a database transaction.
The pause response includes the final committed tick/time.
Repeated pause/resume requests are idempotent; changing a terminal run returns a conflict.

## 6. API Surface

Use FastAPI REST/JSON, generated OpenAPI, and a documented WebSocket schema.
The same process may serve the compiled frontend and API in P0.
Every response error has `{code, message, details, request_id}`; `details` is an array of field paths/reasons and must not include secrets.
Use `422` for invalid configuration, `404` for unknown resources, `409` for lifecycle conflicts, `401/403` for authentication/authorization, and `503` when persistence is unavailable.

| Method and path | Role | Request / response behavior |
|---|---|---|
| `GET /health/live` | local/public | Process responsiveness; no model or DB work. |
| `GET /health/ready` | local/public | Dependencies and pinned ephemeris available, DB reachable, writer initialized. |
| `GET /v1/catalog` | consumer/viewer | Supported model/schema versions and public channel catalog; no scenario catalog. |
| `POST /v1/configurations/validate` | operator | JSON configuration → normalized candidate and all errors; no persistence/run. |
| `POST /v1/configurations` | operator | Configuration → immutable revision ID/hash. |
| `POST /v1/runs` | operator | `{configuration_id}` → created run, allocated streams, sanitized public descriptor. |
| `GET /v1/runs/{run_id}` | viewer | `PublicRunStatus`: lifecycle, committed tick/time, requested/effective speed, wall lag, public satellite descriptors, stream IDs, public model/data provenance. |
| `POST /v1/runs/{run_id}/control` | operator or scoped viewer_control | `{action: start|pause|resume|stop}` or `{action: set_speed, speed: 1|5|20}` → acknowledged state and committed tick. |
| `GET /v1/streams` | consumer | Public streams, source/provenance, satellite identity, retention bounds. |
| `GET /v1/telemetry?stream_id=...&after=...&limit=...` | consumer | Durable paginated frames and opaque next cursor. |
| `GET /v1/events?stream_id=...&after=...&limit=...` | consumer | Durable public operational events and independent next cursor. |
| `GET /v1/runs/{run_id}/snapshot?at=...` | viewer | Consistent committed snapshot; omitted `at` means latest committed time. |
| `GET /v1/runs/{run_id}/trajectory?from=...&to=...&step_s=...` | viewer | Bounded backend orbit-only samples with explicit time/frame/model provenance. |
| `WS /v1/runs/{run_id}/visual` | viewer | Initial snapshot, clock state, bounded batches of committed samples, lifecycle changes. |
| `GET /v1/evaluation/runs/{run_id}/truth` | evaluator | Paginated private truth, censoring, and scenario metadata. |
| `GET /v1/operator/runs/{run_id}/manifest` | operator/evaluator | Full immutable private reproducibility manifest. |

All mutation requests, including run controls, use an `Idempotency-Key`: persist key, request hash, and result; same key/body returns the original response, same key/different body returns `409`.
`PublicRunStatus`, public spacecraft descriptors, snapshots, and visual batches are explicit response models with allowlisted fields, never serialized ORM rows, `RunManifest`, or `SatelliteState` objects.
Public provenance may include orbit/Earth/Sun model identifiers and Earth-orientation coverage status; it must not include scenario names, seed, hidden parameters, private threshold rules, or configuration hashes that serve as evaluation labels.
The one exception is the optional `environment_source` label, which a configuration author sets to name the recorded data behind a run's conditions, such as the Metis demo's `BUPT-1 solar harvest, 21 June 2023 (scaled)`.
Control operations serialize through the single runner command queue; acknowledge only after the command and idempotency result are durably applied at the stated boundary.
Give an unapplied command a five-wall-second deadline; cancellation and application must be serialized so a `503 control_not_applied` response guarantees that command cannot run later.
If it committed but the HTTP response was lost, retrying the same key returns the original acknowledgement.
During persistence retry, reject new controls with `503 control_not_applied` rather than queue them behind a 30-second outage.
Pause/stop process after the current bounded batch commits, returning its final tick; no computed samples are discarded to make a faster acknowledgement.

Read limits default to 500 frames, maximum 2,000; trajectory requests allow at most 10 satellites × 3,601 samples (one hour at 1 s) per request and must lie within the run interval.
Snapshot history is limited to committed telemetry instants; reject future health-state queries.
An orbit-only future trajectory may extend beyond committed telemetry within the configured run interval because it contains no health prediction; label it `predicted_orbit` and never attach future EPS values.
Historical snapshots return the nearest prior committed tick and the actual sample time; do not invent intermediate health values.
The viewer calls snapshot without `at` for current committed playback.
Telemetry charts separately refill the selected window through public replay,
without moving the playback clock. `GET /v1/telemetry` accepts inclusive
`from_sequence` and `through_sequence` bounds (0–86,400) instead of `after`.
The end cannot exceed the captured committed tick; omitted bounds default to
zero and that tick. Each response still contains at most 2,000 frames. Continue
a bounded read with the next numeric range; cursor replay remains unchanged.
Historical `at` is for integration/debug verification; recorded-run UI seek remains P1.

## 7. Delivery, Replay, and Backpressure

**DATA-04:** Durable cursor reads are the mandatory integration protocol.
An analytics connector polls, processes, and saves its cursor after committing its own outputs.
An empty page is successful with the same cursor, not an error.
On first read, omitted `after` starts at earliest retained data; an explicit `after=latest` starts at the current committed tail and returns a cursor even when empty.
Response includes `items`, `next_cursor`, `has_more`, and retained range.
Cursors bind schema/API version, stream/filter, and last committed position; using a cursor with another stream returns `422`.
Retention-expired cursors return `410` with retained bounds and an explicit resynchronization requirement.

Frames are committed before they appear in any public stream.
The immutable frame log is also the P0 durable delivery source, so a separate queue/broker is unnecessary.
Replay returns original frame identity, event timestamps, and provenance.
A page wrapper may include `delivery_mode: replay|live` and current wall time without altering the canonical frame.
Regenerating the same physics allocates new identities and is not replay.
No global ordering across unrelated producers is promised; consumers order each stream by sequence and align streams by event time when needed.

Bound queues: the writer holds at most four complete uncommitted ticks (40 frames at ten satellites), or 16 MiB, whichever is reached first.
Do not advance another batch until the current batch commit is acknowledged; retain its computed outputs unchanged for retry.
At the limit, stop advancing the simulation and surface `persistence_backpressure`; do not drop frames.
A transaction failure rolls back its batch, retains that batch for retry, and leaves the public committed clock unchanged.
If retry cannot succeed within 30 wall seconds, fail the run with its last committed tick; do not emit uncommitted state.
This is a deliberate P0 stop policy, not seamless crash recovery.

The visual stream may coalesce updates and skip intermediate *delivery* frames because the durable log still contains them.
Its typed payloads are `snapshot`, `samples`, `clock`, `lifecycle`, `resync_required`, and `error`, each with `visual_schema_version`, `run_id`, and wall `sent_at`.
`snapshot` contains `PublicRunStatus` and public measurement frames; `samples` contains per-stream sequence ranges and complete public frames; `clock`/`lifecycle` contains only public run status.
No WebSocket payload serializes hidden domain objects or private events.
Publish up to five batches per wall second and keep two wall seconds' worth of committed samples at the active speed plus one bracketing sample for interpolation (41 samples at 20× and 1 Hz).
On speed changes, grow/refill the buffer from committed history before reducing display lag; never jump beyond its time bracket.
Each batch carries sequence ranges and the last committed simulation time.
A slow browser gets a `resync_required` response/current snapshot rather than an unbounded backlog.
On reconnect it loads a fresh clock/snapshot and the small committed history window before animating.
Browser disconnection never pauses physics.

P1 outbound delivery can implement a `TelemetrySink` HTTP batch adapter over the same log with a per-destination cursor.
Use at-least-once delivery, stable identities, bounded exponential retry, receiver deduplication, and explicit rejection handling.
Do not delete accepted local data merely because a remote request failed.
MQTT, NATS, Kafka, CCSDS, or mission protocols belong in adapters justified by a real downstream consumer, not P0 domain objects.

## 8. Persistence

Use **plain PostgreSQL** for the initial service: structured metadata plus one JSONB frame per satellite per simulated second.
Keep frequently filtered identity/time fields in typed columns.
PostgreSQL supports unique/foreign-key constraints and JSONB storage/indexing; this decision uses those mechanisms to avoid a separate metadata database. [PostgreSQL constraints](https://www.postgresql.org/docs/current/ddl-constraints.html), [JSON types](https://www.postgresql.org/docs/current/datatype-json.html)

The [database tables and relationships reference](reference/database.md) generates
the current columns, keys, constraints, indexes, and relationship diagram directly
from SQLAlchemy metadata. Use it for the implemented relational structure rather
than treating JSON payload properties as separate SQL columns.

Private storage holds immutable configuration revisions, run lifecycle/provenance,
scenario truth, and durable idempotency responses. Public storage holds streams,
telemetry frames, and operational events. The current simulator requires every
stream, frame, event, and truth record to reference a run; support for observed-source
API payloads does not make those database references nullable. Configuration,
manifest, status, and payload JSON carry their respective versioned data contracts.

Stream/sequence, stream/time, run/time, and run/sequence indexes support replay and snapshots.
Do not add blanket JSONB GIN indexes for channels without an actual query need.
Repository methods expose append frames, read after cursor, read snapshot, save revision, and transition run; domain objects do not construct SQL.
Use SQLAlchemy with Psycopg and Alembic migrations.
Batch inserts for a bounded number of complete ticks; frames, operational events, private truth for those ticks, and the run's committed tick update must commit atomically.
Batch no more than four ticks or 200 ms wall time, whichever comes first during paced operation; backpressure may delay a commit but must not publish its future state.
The repository checks conflicts by identity: identical canonical frame bytes are a successful duplicate, while the same identity with different canonical payload is an integrity error that stops the producer.
Canonical bytes include `emitted_at` on retries; a regeneration receives a different stream identity.

At 1 Hz, one satellite produces about 86,400 frames per simulated day, excluding the initial t=0 frame.
Three satellites produce 259,200; ten produce 864,000.
At 20×, ten satellites require 200 frames/s and generate 17.28 million frames per wall day if left running.
At an assumed measured-on-implementation size of 2–4 KiB/frame, ten satellites' simulated day is approximately 1.7–3.5 GB before database/index/WAL overhead (decimal GB).
These are capacity calculations, not throughput benchmarks.
Do not store one row per channel; 15 channels would multiply row counts unnecessarily for this initial access pattern.

Default runs last six simulated hours; a configurable maximum of 24 simulated hours protects local storage.
Default terminal-run retention is seven wall days, and no active run may be expired.
`POST /v1/runs` also accepts `retain: boolean` (default false) as immutable administrative metadata, separate from the physical configuration; retained runs are excluded from automatic cleanup.
Retention uses wall termination time, never simulated `observed_at`, and is advertised with stream retained bounds.
The service does not track external consumer progress: consumers must read within retention or request a retained run at creation; an expired cursor returns `410` even if that consumer had not finished.
No silent deletion of active/retained data is allowed; low disk or a configured disk quota stops new advancement with an actionable status.
Record measured bytes/frame and current disk headroom in run statistics.

P1 can export Parquet for offline experiments or add TimescaleDB when larger retained histories/time-bucket queries justify it.
Partitioning/hypertables require redesigning unique constraints to include partition keys as required by the selected engine; do not declare deduplication solved by a key the database cannot enforce.
Neither InfluxDB nor ClickHouse is required for P0; revisit when workload measurements, existing infrastructure, or analytics query patterns outweigh another operational dependency.

## 9. Contract Evolution and Source Replacement

Version configuration, public frame schema, channel catalog, physics model, and scenario separately.
Within `telemetry.v1`, additions must be optional and preserve existing meaning/types/units; new required fields, renamed channels, or changed units require a major contract/catalog change and adapter.
Consumers tolerate unknown optional channels but reject unsupported envelope major versions.
The producer validates strictly before append.

The first implementation must generate machine-readable schemas, golden valid/invalid fixtures, and a consumer example that knows nothing about simulator classes.
One contract gate feeds that consumer both synthetic and observed-source fixtures with no `run_id` on the observed fixture.
The observed fixture is a contract test, not evidence of a working real satellite integration.

To retire the simulator, retain its public measurement contract/catalog conventions, replace producer registration and protocol mapping at the ingestion boundary, and let ingestion own long-term operational storage.
Downstream systems should not query private simulator tables or import its `SatelliteState`.
The viewer is allowed to depend on simulator control APIs; the analytics consumer is not.

## 10. Optional Spacecraft Telemetry Extension

The subsequent `spacecraft.v1` catalog is an explicit profile opt-in through `sensors.catalog` plus `housekeeping`; it does not change the historical `power-leo.v1` P0 channel meanings or require existing profiles to add subsystems.
It contains 41 modeled channels, including the original 15, and 12 unavailable entries emitted with null values and `missing` quality.
The [spacecraft telemetry reference](reference/spacecraft-telemetry.md) specifies model limits and distinguishes this coverage from the supplied 210-field inventory.

The `telemetry.v1` envelope keeps its source/stream/sequence identity and UTC/window semantics.
Catalog-aware validation supports scalar, three-vector, four-vector, and declared string shapes; currently unavailable mission-code strings must remain missing.
Attitude quaternions are Hamilton `[w,x,y,z]`, actively mapping body vectors into GCRS, with successive signs aligned by the satellite composer.
Regulated electrical measurements and payload power/acquisition gates describe the completed interval; temperatures, counters, storage, and attitude describe its endpoint.
Sequence zero advances none of those integrated states.

Each stream persists its immutable catalog version; migration `0003` assigns `power-leo.v1` to existing streams.
`GET /v1/catalog?version=spacecraft.v1` exposes the extension while an omitted version retains the legacy catalog.
`GET /v1/runs/{run_id}/telemetry-report` accepts inclusive `from_sequence`/`through_sequence`, captures a committed boundary, and summarizes only retained public measurements with quality counts and coverage.
Interval integrals use channel-unit seconds and exclude zero-duration or non-valid readings; componentwise quaternion statistics are not attitude averages.
The standalone public [dataset exporter](../examples/export_run.py) preserves frame identities and the captured boundary without including evaluator truth.
Outcome labels and private reproducibility metadata remain separately authorized, and related executions must remain grouped when forming ML splits.

## Metis Demo Agent

The Metis agent (`backend/src/metis_agent`) is mounted when `METIS_MISSION_CONFIG` exists. It never imports the simulator.
Its contracts are generated into `schemas/metis-agent.v1.schema.json` and `frontend/lib/api/metis_generated.dart`.

Every route requires a signed-in viewer session. State-changing routes also require the CSRF token and an `Idempotency-Key`.

| Route | Result |
|---|---|
| `GET /v1/metis/briefing` | `MetisBriefing`: mission, forecast bands in mission watts, proposal with forecast margins, approval window, and the operator's latest run with Metis off and on (`runs.metis_off`, `runs.metis_on`) |
| `POST /v1/metis/proposals/{id}/approve` | `ApprovedPlan` with the Metis plan's task windows, or 409 `uplink_closed` after the window |
| `POST /v1/metis/proposals/{id}/reopen` | `ApprovalWindow`, cleared and reopened for rehearsal; both modes' runs are forgotten |
| `POST /v1/viewer/mission-run {plan, proposal_id?, watch?}` | `ViewerBootstrap` for a run flying `original` or the approved `metis` plan; `watch: true` flies the original plan with Metis on: the run starts at T0 and pauses by itself at the alert (`METIS_ALERT_S`, +60), the pending alert is reported only once the run reaches it, and the approval window restarts; `plan: metis` commits history up to the alert and continues from there; 409 `not_approved` for an unapproved Metis plan; the cookie is rebound to the new run |
| `POST /v1/metis/runs/{run_id}/dismiss` | `MetisAlert`, dismissed; 409 `alert_not_pending` when there is no pending alert |
| `GET /v1/metis/runs/{run_id}/outcome` | `RunOutcome` from public frames and events: margin, task states (`pending`, `running`, `done`, `skipped`), downlink progress and delivery time, `metis_on` and the alert; 404 for a run this operator did not launch |

**Data boundary:**
- Metis reads only its allowlisted decision artifact (no realized values) and public run status, frames and events.
- Each demo run is created server-side from `configs/metis-wildfire.yaml` with its private scenario. The browser chooses only the plan; it can neither read that scenario nor supply it.
- An edit through `/v1/viewer/configuration` still strips the scenario.
- Approval state and the run registry are held in memory per operator.
