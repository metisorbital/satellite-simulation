# Independent review of the normative physics model

Reviewed: `docs/physics-model.md` and `docs/contracts.md` as they existed on 2026-09-21.

Scope: equations, reference frames, time advancement, interval/sample semantics, power feasibility, Cesium inputs, and acceptance gates. This review does not request optional higher-fidelity physics.

## Verdict

The orbit, eclipse, panel, and battery equations are internally sound for the declared P0 approximation. The example is physically plausible and likely reaches the intended reserve outcome near the end of the six-hour run. The blocking issues are contract semantics: interval-average power is not representable in the current public envelope, the t=0 allocation is undefined by the stated equations, and tick-boundary ordering remains easy to implement one tick early or late.

## Findings

### F1 — High: the public envelope cannot express the physics model's sample window

Evidence:

- `physics-model.md:178-181` defines flow/power fields as interval averages ending at `observed_at`, endpoint fields at `observed_at`, and requires `sample_window_s=0` at t=0 and `1` thereafter.
- `contracts.md:83-97` has no `sample_window_s` field.
- `contracts.md:102` says the catalog declares cadence and origin, but no temporal aggregation semantic.
- `contracts.md:112-126` does not distinguish endpoint values from interval means.
- The example at `contracts.md:135-158` also omits the required window.

Impact: a consumer cannot determine whether `eps.solar_power_w` is instantaneous at the endpoint or averaged over the previous interval. It can incorrectly join endpoint `mode` and `illumination_fraction` to power that was accumulated under the preceding mode or midpoint illumination. Replay preserves the numbers but loses their physical meaning.

Required correction:

1. Add required nonnegative `sample_window_s` to `telemetry.v1`. For P0 it is `0` on sequence 0 and `1` on all later frames.
2. Define `observed_at` as the right edge of that window.
3. Add a catalog property such as `sample_semantics: endpoint | interval_mean | instantaneous` per channel. Orbit, geodetic state, illumination, incidence, battery energy, SOC, and envelope `mode` are `endpoint`; EPS flow/power fields are `interval_mean`; the t=0 power allocation is `instantaneous`.
4. State that the envelope window applies to channels whose catalog semantic is `interval_mean`; endpoint channels still represent `observed_at`.
5. Add the field to the JSON example and golden schemas/fixtures.

This change is required before freezing `telemetry.v1`; adding it later as a required field would force a major contract revision under `contracts.md:318-321`.

### F2 — High: t=0 power allocation divides by a zero-duration interval

Evidence:

- `physics-model.md:157-175` limits battery charge/discharge by terms containing `1/dt_h`.
- `physics-model.md:181` requires a t=0 instantaneous power allocation with `sample_window_s=0` and no energy advancement.

At t=0, `dt_h=0`, so `(C-E)/(eta_c*dt_h)` and `E*eta_d/dt_h` are undefined. A branch is implied but not specified.

Required correction: normatively define sequence 0. One consistent rule is:

- compute instantaneous generation and requested load at the epoch;
- keep `E_next=E` unconditionally;
- apply charge/discharge rate caps and forbid charging if `E=C` or discharging if `E=0`;
- omit the energy-over-window cap because no integration window exists;
- mark the flow fields `instantaneous` through `sample_window_s=0` plus catalog semantics.

Alternatively, mark all power-flow channels missing at sequence 0. Do not pass `dt=0` into the interval equations. Add a full/empty/interior t=0 acceptance case.

### F3 — High: tick-boundary ordering is not yet unambiguous across the two documents

Evidence:

- `physics-model.md:179-185` intentionally reports preceding-interval power and the new endpoint mode when a schedule change occurs at the endpoint.
- `physics-model.md:296` defines operations as `[start_s,end_s)`.
- `contracts.md:163-165` says to apply operations/faults before state advancement, without naming whether the command time is the interval start or target endpoint.
- `contracts.md:195-197` defines completed ticks and tick-aligned commands but does not close this ordering gap.

An implementation advancing “to tick 3600” can apply the operation starting at 3600 before integrating 3599→3600, while the physics appendix requires that interval to use the old mode and the endpoint frame to show the new mode. Both readings fit the current prose.

Required correction: specify the transition with indexed times. For example:

1. Start from committed endpoint state at `t_k`.
2. Select schedule/fault values active on `[t_k,t_{k+1})`.
3. Evaluate midpoint environment/generation and integrate energy over that interval.
4. Compute endpoint orbit/environment/energy at `t_{k+1}`.
5. Apply/report discrete endpoint mode effective at `t_{k+1}` and emit its event.
6. Commit a frame at `t_{k+1}` whose interval-mean powers describe `[t_k,t_{k+1})` and whose endpoint fields describe `t_{k+1}`.

The current `(t-dt,t]` notation should become `[t-dt,t)` for discrete schedule ownership, or explicitly use left-limit schedule values at the right endpoint. Add boundary fixtures at operation start, operation end, fault control points, pause, and t=0; ordinary bus-balance tests will not detect a one-tick phase error.

### F4 — Medium: the public example is cross-field inconsistent with the only declared baseline profile

Evidence:

- The normative profile has 400 Wh usable capacity and loads of 150/210/70 W (`physics-model.md:247-258`).
- The event reuses `METIS-01` and the baseline epoch but reports `battery_energy_wh=84` and `battery_soc=0.7`, implying a 120 Wh capacity, and `load_requested_w=30`, which is not a configured mode load (`contracts.md:135-156`).

The bus balance inside the fragment is correct: `70 + (-40) = 30 + 0`. The fragment is nevertheless inconsistent with the surrounding baseline and cannot become a meaningful golden fixture or cross-field validator.

Required correction: either make the event explicitly producer-neutral with a separately declared 120 Wh/30 W descriptor and unrelated identity, or update it to values consistent with the 400 Wh profile and one of its allowed loads. Include `sample_window_s` and clarify whether it is intended to be a full-frame golden fixture or only a shape example.

### F5 — Medium: two acceptance gates are not reproducible yet, and no gate covers interval semantics

Evidence:

- P-03 (`physics-model.md:347`) does not specify the centered finite-difference step, so its 0.02 m/s velocity tolerance can produce different results depending on the test author.
- P-04 (`physics-model.md:348`) names no exact published fixture, timestamp, input state, expected output, data version, or tolerance.
- P-06 validates balances, but not whether a schedule/fault was applied to the correct interval.

Required correction:

- Pin the P-03 difference interval and evaluation points.
- Commit the exact P-04 source fixture and expected numbers/checksum alongside the IERS manifest.
- Add a temporal-semantics gate covering sequence 0, `sample_window_s`, one mode start/end, one fault point, and the relation between endpoint fields and interval-mean fields.

## Scientific checks that passed review

- The generalized J2 acceleration in `physics-model.md:84-93` reduces to the standard component form when the pole vector is `[0,0,1]`; dimensions and signs are correct.
- Transforming the ITRS +Z pole into GCRS at the epoch and holding it fixed creates a declared conservative short-arc approximation. Defining osculating elements against GCRS X/Y remains mathematically valid, though inclination and RAAN are therefore not equator-of-date elements. The document already avoids claiming that 97.6° is a verified Sun-synchronous design.
- The finite-Sun/spherical-Earth eclipse geometry in `physics-model.md:114-128` has the correct full-light, containment, and partial-overlap branches. Explicit containment handling avoids the partial-overlap singularity.
- The LVLH axes in `physics-model.md:130-135` are right-handed: `+Z` nadir, `+Y` opposite angular momentum, and `+X=+Y×+Z`. For circular prograde and retrograde cases, `+X` follows the velocity direction.
- The solar-power equation is dimensionally correct. Ideal two-axis tracking makes incidence one by prescription while retaining a clean extension point for later panel policies.
- The battery equations and the two balances in `physics-model.md:160-193` are correct with the declared sign convention. Charge/discharge efficiency is applied on the storage side, and the energy-limited powers prevent hidden clipping.
- Passing ITRS position and the corresponding rotating-frame derivative to Cesium fixed-frame Hermite interpolation is consistent with the documented visualization contract.

## Example feasibility check

The example is plausible; no parameter change is justified before executing the real model.

From the normative values:

```text
face-on bus generation = 1361 * 0.9 * 0.28 * 0.95 = 325.8234 W
two-body period at a=6,928,137 m = about 95.65 min
```

Using an illustrative 35-minute eclipse gives about `+90.2 Wh/orbit` when healthy and `-156.8 Wh/orbit` after derating to 0.25 at the nominal 150 W load. The battery has 280 Wh between initial 85% SOC and the 15% reserve, while healthy charging can reach the 400 Wh ceiling before the late degraded phase.

As a non-normative independent sanity calculation, a one-second central+J2 propagation with an approximate equinox Sun vector, the documented schedule, eclipse geometry, power limits, and fault ramp placed reserve entry near `t=20,625 s`, confirmation near `t=20,685 s`, and end SOC near 4.3%. This is comfortably inside the 21,600-second run but is not an acceptance result because it did not use the pinned Astropy/IERS implementation or midpoint integration. The committed simulator must still run P-10 and preserve the resulting trace as the calibrated fixture.

## Resolution verification — 2026-09-21

This bounded follow-up reviewed only the normative changes made for F1–F5. No additional science experiment was run.

- **F1 — Resolved.** The event contract now requires `sample_window_s` and `interval_mode`; the channel catalog declares endpoint versus interval-mean sampling; the sequence-zero instantaneous exception is explicit; and the example carries both fields.
- **F2 — Resolved.** The sequence-zero branch now forbids the `dt_h`-dividing formulas, defines rate- and boundary-limited instantaneous allocation, leaves energy unchanged, and does not advance dwell time. P-12 covers empty, full, and partially full initial batteries.
- **F3 — Resolved.** The physics appendix gives an indexed interval order: use the mode active at `t_k`, evaluate the derating modifier at the midpoint, integrate, then apply and report endpoint operations and outcomes. `interval_mode` preserves the completed interval's ownership when endpoint `mode` changes, the contract defers to this authoritative order, and P-12 checks the load and fault boundaries.
- **F4 — Resolved.** The event is explicitly labeled a protocol-only example rather than a calculated run sample. Its 400 Wh capacity, 0.7 SOC, 280 Wh energy, 150 W requested/served load, and `200 - 50 = 150` bus balance are mutually consistent.
- **F5 — Resolved.** P-03 pins centered-difference steps at 0.1 s and 0.05 s; P-04 pins the ERFA/SOFA source revision, complete inputs, expected matrix, test vector, and tolerances; and P-12 supplies the missing temporal-boundary gate.

**Remaining blockers in the reviewed scope: none.**
