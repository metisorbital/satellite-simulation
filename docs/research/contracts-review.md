---
title: Contracts and Physics Implementation Review
description: Identify contradictions and implementation gaps in the proposed configuration, telemetry, persistence, lifecycle, delivery, and physics contracts.
content-type: reference
audience: engineering
status: independent review
date: 2026-09-21
---

# Contracts and Physics Implementation Review

## Review Scope

This review covers [Configuration and Data Contracts](../contracts.md) and [Physics Model and Visual Consistency](../physics-model.md) as an implementation handoff.
It checks whether one team can implement the same time, power, lifecycle, persistence, replay, and viewer behavior without making undocumented choices.

Severity means:

- **Critical:** normative statements select incompatible behavior or can break the causal telemetry story.
- **High:** a common implementation can fail a stated P0 outcome or acceptance gate.
- **Medium:** an interoperability, validation, or test choice remains unspecified.

The selected P0 architecture is otherwise coherent: one process and writer, plain PostgreSQL, one wide frame per satellite/tick, no broker, one progressive solar-array fault, no invented circuit channels, source-neutral telemetry, and separately authorized truth.

## Findings

### C-01: A Frame Can Attribute the Previous Power Window to the New Mode

**Sources:** [contracts §3–4](../contracts.md#3-public-measurement-envelope), [physics §5](../physics-model.md#5-balance-power-and-integrate-battery-energy)

The frame now correctly carries `sample_window_s`, but the control applied during that window remains ambiguous.
The contracts order says to apply schedules/fault modifiers before state advancement.
The physics appendix also says that when an interval ends at a scheduled mode change, its power comes from the previous mode while the frame reports the new endpoint `mode`.
At that boundary, an analytics consumer joining fields within one frame will attribute old-mode load/power to the new mode.
`sample_window_s` identifies the window length but not the control state used over it.

The progressive fault has a related ambiguity: generation is an interval-average midpoint quantity, while “apply fault modifiers at the interval start” can be read as evaluating the piecewise-linear multiplier at the left endpoint.
Those choices produce different energy and truth near control points.

**Action:** Add one normative step table for advancing `S_k` at `t_k` to `S_{k+1}` at `t_{k+1}`.
Define the interval as `[t_k,t_{k+1})` or `(t_k,t_{k+1}]`, the schedule state used during it, when a transition becomes effective, and where the linear derating is evaluated.
For a correlated frame, either make `mode` mean the mode used for the reported power window or add an explicit `interval_mode`; keep the exact endpoint transition in `mode_changed`.
Evaluate the continuous derating at the same midpoint as generation, while private truth may record its endpoint value separately.
Add a golden test with mode start/end and a derating control point on adjacent ticks.

### H-01: The Initial Power Allocation Is Undefined at `sample_window_s=0`

**Source:** [physics §5](../physics-model.md#5-balance-power-and-integrate-battery-energy)

The battery equations limit charge/discharge using terms divided by `dt_h`.
The t=0 frame requires an “instantaneous power allocation” with `sample_window_s=0`, which makes those terms undefined.
Implementations may divide by zero, substitute one second, or publish different full/empty-battery behavior.

**Action:** Specify a t=0 branch.
One simple rule is to compute instantaneous generation/load and apply charge/discharge power caps plus the exact empty/full boundary, without an interval-energy limit or energy update.
Alternatively, mark interval-average allocation channels missing at t=0 and publish only endpoint state/instantaneous source/load channels.
Whichever rule is selected, add t=0 fixtures for empty, partial, and full batteries.

### H-02: Commit Batching and Control Latency Do Not Share a Bound

**Sources:** [contracts §5](../contracts.md#5-run-and-time-semantics), [contracts §7–8](../contracts.md#7-delivery-replay-and-backpressure), [physics §8](../physics-model.md#8-visualize-the-authoritative-state)

Pause must take effect at a committed tick boundary, control calls must return a bounded outcome, the viewer targets at most 0.5 wall seconds of lag at 20×, and persistence commits a bounded but unspecified number of complete ticks.
At the same time, the writer may hold 2,000 uncommitted frames.
At ten satellites this can represent 200 simulated ticks, or ten wall seconds at 20×.

It is unclear whether the runner may advance physical state that far beyond the public committed clock, whether pause drains that backlog, whether stop discards it, and how a control command is handled while a failed batch is retrying for up to 30 seconds.
A queue bound is not a commit-latency bound.

**Action:** Define a maximum speculative/transaction batch in complete ticks and a wall-time flush bound, then service control commands between those batches.
For example, commit after at most five ticks or 250 wall milliseconds, whichever is reached first; the exact numbers should be validated against the 0.5-second viewer target.
Define whether in-memory state ahead of the last commit is checkpointed for retry, how pause/stop behaves during database retry, and whether a timed-out command is canceled or can still apply later.
Give every control request a stable command ID or idempotency key so response loss cannot create an ambiguous second command.

### H-03: The Visual Buffer Is Too Ambiguous to Satisfy the Playback-Lag Rule

**Sources:** [contracts §7](../contracts.md#7-delivery-replay-and-backpressure), [physics §8](../physics-model.md#8-visualize-the-authoritative-state)

The WebSocket keeps a “two-second committed sample buffer,” without saying wall or simulated seconds.
At 20×, the viewer's target 0.5 wall-second playback lag places display time about ten simulated seconds behind the committed tail.
A two-simulated-second buffer cannot contain that display time; a two-wall-second-equivalent buffer can.

**Action:** Define the buffer in both domains.
A direct rule is “at least two wall seconds worth at requested speed,” which is 40 one-second samples per stream at 20×, plus the adjacent sample needed for interpolation.
Specify how the buffer resizes on speed changes and add reconnect/stall tests at 1×, 5×, and 20×.

### H-04: The Five-Minute Demo Plan Requires a P1 Viewer Capability

**Sources:** [contracts §6](../contracts.md#6-api-surface), [physics §7](../physics-model.md#7-baseline-configuration-example)

The physics appendix says to replay a prepared excerpt at 20× for a five-minute presentation.
The contracts explicitly limit the P0 viewer to the latest committed buffer and keep recorded-run seek in P1.
The durable cursor API can replay data to an integration consumer, but no P0 API/viewer contract turns that history into a synchronized globe-and-health playback.

**Action:** Preserve P0 scope by changing the demo procedure: pre-run the simulation to the desired committed tick, pause it, open the latest snapshot, then resume at 20× during the presentation.
If true recorded playback is required, promote a bounded playback mode to P0 and specify its clock and WebSocket semantics rather than relying on the analytics replay endpoint implicitly.

### H-05: Public Limit Events Have No Public Configuration or Transition Rule

**Sources:** [contracts §4](../contracts.md#4-truth-and-operational-events), [physics §6](../physics-model.md#6-define-the-first-fault-outcome)

P0 operational events include `low_energy_limit_entered`, `low_energy_limit_cleared`, and `power_unserved`.
The only reserve threshold in the configuration example is the private evaluation outcome, and the physics appendix correctly says a public limit must use a separate, explicitly public definition.
No public limit schema exists.
`power_unserved` also does not say whether it fires every nonzero tick or only on a state transition, nor how it clears.

**Action:** Either remove low-energy public events from P0 or add an allowlisted public operational-limit section outside `scenario`, with entry/clear comparisons and hysteresis.
Do not default it from the private reserve outcome.
Define unserved-power events as transitions, such as `power_unserved_entered` and `power_unserved_cleared`, or explicitly define per-tick emission if that is intended.
Add boundary tests for exact equality and clear behavior.

### H-06: `aborted` Is Used as a Terminal State but Is Missing From the State Machine

**Source:** [contracts §5](../contracts.md#5-run-and-time-semantics)

The declared state graph contains `created`, `running`, `paused`, `completed`, `stopped`, and `failed`.
The following paragraphs make `aborted` a terminal recovery state and use it in truth censoring.
Generated API schemas, database constraints, viewer status handling, and retention code cannot implement both descriptions without guessing whether `aborted` is a state or merely a censor reason.

**Action:** Add `aborted` to the normative run-state enum and graph as the recovery result for a persisted `running`/`paused` run whose process died before it could commit a terminal transition.
Include it in `PublicRunStatus`, database checks, lifecycle WebSocket messages, retention eligibility, and terminal-state tests.
Keep `failed` for an unrecoverable error whose terminal transaction did commit.

### H-07: Time-Based Retention Cannot Promise to Preserve “Unconsumed” Data

**Sources:** [contracts §7–8](../contracts.md#7-delivery-replay-and-backpressure)

External consumers own and persist opaque cursors; the service has no registered-consumer checkpoint.
The persistence section nevertheless prohibits silent deletion of “unconsumed” data while also setting seven-day completed-run retention and `410` behavior for expired cursors.
The service cannot know whether an external consumer has consumed a frame.
The operator `retain` flag also lacks an API/location and appears to conflict with terminal run immutability if it is changed after completion.

**Action:** For P0, state that retention is advertised and wall-time based regardless of external consumer progress; consumers must react to retained bounds and `410`.
Remove the unconsumed-data guarantee unless named consumer registrations are added.
Define `retain` as separately mutable administrative retention metadata, or make it an immutable run-creation field with a documented operator endpoint before execution.

### M-01: The Configuration Contract Does Not Enumerate All Fixed P0 Values

**Sources:** [contracts §2](../contracts.md#2-configuration-rules), [physics §1–7](../physics-model.md#1-define-what-accurate-means)

Requirements are scattered across the appendices, but the validation section does not collect the exact P0 constraints for `tick_s`, `telemetry_period_s`, duration/default/maximum, speed, Earth/orbit/Sun model IDs, panel-pointing type, fault type, and outcome type.
An implementation could schema-validate values that the runner does not support.

The contracts currently allow one fault modifier **per satellite/target**, which permits several concurrent faults in a ten-satellite run, while P0 is scoped to one progressive fault.
They also allow overlapping safe-mode intervals through an “explicit priority” that has no configuration representation or resolution algorithm.

**Action:** Add a P0 validation matrix in the configuration section.
Require `tick_s=1`, `telemetry_period_s=1`, speed in `{1,5,20}`, duration as an integer tick count up to 86,400 seconds, the selected model IDs, `ideal_sun_tracking`, and at most one `solar_derating` scenario entry for the whole run.
For KISS, reject all overlapping operational intervals in P0; defer safe-mode priority until its schema and deterministic resolution are defined.

### M-02: JSON Sequence Interoperability Has No Numeric Limit

**Source:** [contracts §3–4](../contracts.md#3-public-measurement-envelope)

Frame and event sequences are JSON integers, and clients are told to reject values beyond their “exact integer range.”
That range is not a contract value and differs by implementation; JavaScript loses exactness above `2^53-1` while Python integers do not.

**Action:** Set the numeric contract maximum to `9,007,199,254,740,991` (`2^53-1`) for frame/event sequences, or encode them as decimal strings.
Apply the same decision to cursor payloads if a cursor ever exposes a numeric position.

### M-03: Canonical Configuration Hashing Needs a Named Algorithm

**Sources:** [contracts §2](../contracts.md#2-configuration-rules), [contracts §5](../contracts.md#5-run-and-time-semantics)

Normalization sorts keyed collections and hashes canonical JSON, while reproducibility projections use sorted-key JSON.
Float formatting, Unicode normalization, negative zero, separators, and duplicate-key handling can still produce different hashes across serializers or language ports.

**Action:** Name a canonicalization algorithm such as RFC 8785 JSON Canonicalization Scheme, or pin an exact backend serialization procedure with encoding, separators, float rules, and test vectors.
Use the same procedure for configuration hash and idempotency request hash where their inputs overlap.

### M-04: The Absolute Frame-Transform Gate Is Not Yet Executable

**Source:** [physics §9](../physics-model.md#9-numerical-and-visual-acceptance-gates)

P-04 requires an independent published/reference fixture but does not name its epoch, input GCRS state, expected ITRS state, Earth-orientation inputs, source/version, or tolerance.
Different implementers can select fixtures of very different quality and all claim the gate passed.

**Action:** Commit one fixture definition before implementation sign-off.
Include input epoch/state, pinned IERS data, expected transformed state/velocity, authoritative source or independent tool/version, and numeric tolerance.
Keep the round-trip P-03 test as a separate invariant.

## Recommended Resolution Order

1. Resolve C-01 and H-01 before writing domain models; they determine frame meaning and step equations.
2. Resolve H-02 and H-03 before implementing the writer or WebSocket; they determine batching, controls, and buffer sizing.
3. Resolve H-05 and H-06 before generating Pydantic/OpenAPI/database enums.
4. Resolve M-01 through M-03 before publishing configuration and telemetry schemas.
5. Resolve H-04, H-07, and M-04 before the integrated demo and acceptance report.

## Resolution Verification

Verified 2026-09-21 in one bounded reread of the changed contract and physics sections. The original findings above remain as audit history; this table records their current disposition.

| Finding | Status | Verified resolution |
|---|---|---|
| C-01 | Resolved | Frames now carry `sample_window_s` and required `interval_mode`. The normative step order fixes interval-start operations, midpoint fault/environment evaluation, energy integration, endpoint operations/outcomes, and measurement persistence. Physics P-12 checks the boundary behavior. |
| H-01 | Resolved | Sequence zero now has an explicit no-advance allocation branch with `sample_window_s=0`, guarded charge/discharge formulas, unchanged energy, and no dwell-timer advancement. |
| H-02 | Resolved | A batch is bounded to four complete ticks or 200 ms, the runner cannot advance another batch before commit acknowledgement, and failed batches are retained unchanged for retry. Controls are serialized and durably acknowledged, have a five-second cancellation deadline, are idempotent, and are rejected during persistence retry. |
| H-03 | Resolved | The visual buffer is defined as two wall seconds at active speed plus one interpolation sample: 41 samples at 20x and 1 Hz. Speed changes require growth/refill from committed history before display lag is reduced. |
| H-04 | Resolved | The P0 demo procedure now pre-runs, pauses at a suitable committed point, opens the current snapshot, and resumes at 20x. Recorded seek remains explicitly P1, consistent with the latest-snapshot viewer contract. |
| H-05 | Resolved | Optional `public_limits` has a bounded schema, hysteretic enter/clear semantics, and P0 channel restriction. `power_unserved` now emits only on inactive/active transitions with a defined public payload. Private scenario thresholds remain excluded. |
| H-06 | Resolved | `aborted` is in the complete normative enum and recovery transition, and the contract applies that enum to responses, database checks, lifecycle messages, retention, censoring, and terminal-state tests. |
| H-07 | Resolved | Retention is advertised, uses wall termination time independent of client progress, and returns `410` when a cursor expires. `retain` is immutable run-creation administrative metadata, with active and retained runs protected from cleanup. |
| M-01 | Resolved | The configuration section now provides fixed P0 values and ranges, permits at most one scenario for the whole run, and rejects all operational schedule overlaps. |
| M-02 | Resolved | Frame and event sequences are limited to `9,007,199,254,740,991` (`2^53-1`), with a new stream required before rollover. |
| M-03 | Resolved | Configuration, projection, and request hashing now name RFC 8785 JCS over normalized UTF-8 JSON and record the canonicalization/schema version. |
| M-04 | Resolved | P-04 now pins an ERFA/SOFA source commit, exact two-part TT/UT1 dates, polar-motion inputs, expected matrix, nonsymmetric test vector, and independent numeric tolerances. P-03 separately covers the production UTC/IERS and velocity path. |

All twelve findings are resolved. No blocker, high, or medium finding remains open from this review.
