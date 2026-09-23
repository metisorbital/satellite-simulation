# Initial Review of Specification and Contracts

Reviewed 2026-09-21 against the current [specification](../specification.md) and [contracts](../contracts.md) only.
The physics appendix and the remaining architecture/validation material were intentionally not reviewed in this pass.
The review respects the declared P0: one solar-array derating fault, energy-only EPS, no ground stations, and no recorded-run UI seek.

## Initial Assessment

The scope is substantially stronger and more feasible than the six-subsystem/four-fault proposal.
It has one causal chain, a useful three-satellite demonstration, a real public/private data boundary, and unusually concrete delivery/persistence semantics.
The P0 still has a few contract ambiguities that can cause a junior or mid-level engineer to accidentally violate replay, truth secrecy, or event ordering.
Resolve the findings below before treating these documents as an unambiguous implementation baseline.

## Findings Requiring Resolution

### P0-1: Define What “Reproduce” Means for a New Run

**Where:** `RUN-01`, “Reproduce a Developing Failure,” `DATA-03`, and “Run and Time Semantics.”

The documents promise reproducibility from manifest and seed, while also requiring every regenerated run to receive new stream UUIDs and setting `emitted_at` to the producer's real wall time.
Those fields necessarily differ across executions.
An implementer cannot know whether the acceptance comparison is expected to include identities/wall timestamps, numerical physics outputs only, or public payloads after excluding transport metadata.

Define a canonical reproducibility projection: fixed-tick, public physical channels/events and private truth values, compared after excluding `run_id`, stream IDs, `sequence` only if identity allocation changes, and wall-time fields such as `emitted_at`/`committed_at`.
State the tolerances and serialisation/canonicalisation rule there or in the validation section.
This does not add a feature; it makes `RUN-01` testable.

### P0-2: Make the Viewer Run Response an Explicit Public Projection

**Where:** `GET /v1/runs/{run_id}`, `RunManifest`, `SatelliteState`, and `FLT-02` access rules.

The endpoint says its response contains “State” and public satellite descriptors, but `SatelliteState` owns fault-modifier state and `RunManifest` owns resolved private configuration.
The surrounding prose says those objects must not be exposed, yet “State” is not a defined API response model.
Serialising a domain object or ORM row would leak a scenario name, hidden derating factor, threshold, seed, or future schedule.

Name the endpoint response `PublicRunStatus` (or equivalent) and enumerate its allowed fields: lifecycle, committed tick/time, requested/effective speed, public descriptor IDs, and stream IDs.
Require its implementation to use a response model separate from `RunManifest` and `SatelliteState`, with a negative access test for every private scenario field.

### P0-3: Specify Operational Event Stream Identity and Cursor Scope

**Where:** `OperationalEvent` in “Objects and Responsibility,” `GET /v1/events`, `DATA-04`, and the `operational_events` table.

Frames have a fully defined identity: `(source_id, stream_id, sequence)`.
Operational events are described as having “their own ordered stream” and “own event identity/sequence,” but their endpoint accepts a telemetry `stream_id` and the table only says “satellite/stream reference.”
It is unclear whether events share the telemetry stream ID and use a separate event sequence, or whether they have an independent event-stream ID.
That changes cursor validation, uniqueness constraints, reconnection logic, and the event schema.

Choose one P0 rule explicitly.
The smallest consistent choice is one event stream per satellite telemetry stream, with a distinct `event_sequence` beginning at zero and an event cursor bound to `(telemetry_stream_id, event_sequence)`.
State that sequence in the event envelope/table and keep it separate from telemetry-frame sequence.

### P0-4: Complete Terminal Truth/Censoring Semantics for Failed Runs

**Where:** `FLT-02`, “Run and Time Semantics,” and “Persistence.”

Truth records must mark every unfinished/healthy run right-censored, but the permitted censor reasons are `duration_reached`, `stopped`, and `aborted`.
The lifecycle also has a terminal `failed` state when retry/persistence failures occur.
The atomic tick-commit rule does not define the terminal transaction that writes censoring when `stop`, `failed`, or process-restart `aborted` occurs.

Add `failed` as a censor reason, or explicitly classify failed output as invalid and excluded from evaluation.
For each terminal non-failure outcome, require one atomic final state transition plus a truth record at the last committed simulation time.
This prevents an evaluator from silently treating a truncated fault run as healthy or complete.

### P0-5: Keep Historical Snapshot Capability Out of the P0 Viewer Flow

**Where:** `EXT-02`, `GET /v1/runs/{run_id}/snapshot?at=...`, and “Inspect the Same State Visually and Numerically.”

P1 defers recorded-run UI seek, but P0 exposes historical snapshots at any committed `at` and describes returning the nearest prior frame.
The API can be a legitimate integration/debug read, yet an implementer may treat it as the UI’s scrub/seek mechanism because the viewer already consumes run snapshots.

State that the P0 viewer calls snapshot without `at` and renders only latest committed state plus the small visual buffer.
The historical `at` parameter is a non-UI read contract for replay/integration verification; no P0 browser control changes it or pauses/scrubs a recorded run.
This preserves the existing P1 boundary without removing the durable-read capability.

## Important Implementation Clarifications

These are not new capabilities; they are details already implied by the current scope that should be made explicit in the remaining validation/architecture text.

| Topic | Clarification needed for atomic implementation |
| --- | --- |
| Deterministic noise | Specify a stable per-satellite seed derivation from the run seed and stable satellite ID, rather than relying on iteration order or a process-global random generator. |
| Control action timing | `stop` must identify the final committed tick in the same way pause does, and completion/stop/failure must never expose a future in-memory state through snapshot or WebSocket. |
| Public visual batches | Define `WS /visual` payloads as a subset/projection of committed public frames and public events only. “Committed samples” must never mean serialised `SatelliteState` or truth records. |
| Limit events | `low_energy_limit_entered` is public because it reports an observed present condition. Keep the private failure criterion and future outcome time out of its reason code, event payload, and UI copy. |
| Fault schedule configuration | The root `scenario` section is required but may be an empty private list; the “optional scenario” wording in the author flow should mean optional content, not an optional root field. |

## Scope and Feasibility Check

The functional physics scope is appropriate for a hackathon: three independently propagated satellites, one profile, 1 Hz frames, energy-based EPS, and one progressive solar derating scenario.
Do not reintroduce voltage, ground passes, a second fault, or another subsystem to resolve any finding above.

The delivery/persistence/security surface is the main schedule risk, not the simplified physics.
FastAPI, PostgreSQL migrations, revision hashing, immutable frame commits, cursors, WebSocket coalescing, and three access roles are all justified by existing P0 requirements, but they need to be built as narrow adapters around the single runner rather than expanded into a generic platform.
The one-active-run and one-writer constraints are the correct guardrails for that work.

## Items Already Consistent

- One solar-array derating fault is correctly separated from public telemetry labels and changes the physical model before measurement.
- Energy-only EPS does not expose battery voltage/current in P0; the catalog instead supplies solar/load/battery-power/energy/SOC terms needed to check balance.
- Ground-station delivery windows are P1 and do not appear in P0 channels or APIs.
- `stop`/regenerate semantics avoid hidden mid-run checkpoint recovery, while normal replay returns committed original frame identities.
- The catalog distinguishes a derived or synthetic value from private model state and prohibits NaN/Infinity/magic missing values.
- The public/private truth boundary names credentials, schemas/roles, response models, and negative tests instead of relying on UI hiding alone.

## Final Review

Reviewed 2026-09-21 after the main specification and its physics/contracts appendices were completed.
This section supersedes the “findings requiring resolution” status above.
No application, database, telemetry execution, calibration result, or performance benchmark was present to inspect.
The documents now state that limitation directly, including in the main document status and the physics appendix.

### Resolved Initial Findings

| Initial finding | Resolution verified |
| --- | --- |
| P0-1 Reproducibility | The contracts define a sorted-key canonical trace projection, preserve deterministic sequence, exclude generated IDs/wall metadata, provide numerical gates, and derive stable per-satellite/channel NumPy random streams. |
| P0-2 Public run projection | `PublicRunStatus`, snapshot, descriptor, and visual-batch responses are explicit allowlisted models and must never serialise `RunManifest`, `SatelliteState`, ORM rows, or private truth. |
| P0-3 Event identity | Operational events now use the associated telemetry `stream_id` plus a separate `event_sequence`, with an explicit envelope, primary key, and cursor namespace. |
| P0-4 Terminal truth | Both truth and terminal-lifecycle sections now use the same `duration_reached`, `stopped`, `failed`, and `aborted` censor reasons, and define atomic recovery handling. |
| P0-5 No P0 UI seek | The viewer calls snapshot without `at`; historical snapshots are retained only for integration/debug verification and recorded-run UI seek stays P1. |

### Resolved Browser-Control Boundary

The contracts now define `viewer_control` as a distinct, server-issued principal with an expiring same-origin session, one bound `run_id`, and an explicit allowed-action set.
The existing control route permits only a broad operator or the exact matching scoped principal; it rejects other runs/actions, checks expiry server-side, closes an expired WebSocket session, and keeps configuration/private routes unavailable.
The credential transport and issuance boundary are also concrete: HttpOnly/SameSite cookies, Secure on HTTPS, Origin/CSRF checks, and grants minted only through the deployment authentication adapter during operator-authorized setup.
This resolves P0-B1 without adding an account API or expanding P0 identity scope.

### Final Conclusion

There are no remaining scope/integration blockers in this review.
The design is internally coherent and implementable as the stated simulator rather than as a premature analytics platform.
The P0 boundary remains sound: a shared-clock 1–10-satellite configurable service, three-satellite demo, J2/Sun/eclipse-to-energy causal chain, one hidden solar-derating scenario, public measurements, private evaluation truth, and a synchronized viewer.
It does not claim calibrated model accuracy, a successful demo outcome, prediction performance, or any delivered application.

The main residual execution risk is the deliberately included persistence/access/visual synchronization work, which is constrained by one process, one writer, PostgreSQL transactions, bounded queues, explicit response projections, and milestone gates.
It should be implemented in the documented vertical slice order before any P1 subsystem or fault is considered.

Related specialist records: [physics review](physics-review.md) and [contracts review](contracts-review.md).
