---
title: Physics Validation Evidence
description: Reproduce the measured orbit, coordinate, eclipse, power, and matched-scenario numerical checks and understand their limits.
content-type: reference
audience: engineering and satellite operations
status: executed numerical evidence
date: 2026-09-23
last-verified: 2026-09-23
related:
  - ../physics-model.md
  - ../contracts.md
  - ../specification.md
---

# Physics Validation Evidence

The final numerical suite passed **80 tests in 112.45 seconds** on the machine below.
It verifies the declared synthetic orbit-to-power approximation against independent analytic, adaptive-integration, published-matrix, and area-quadrature references.
It does not establish flight ephemeris accuracy or complete the service/browser acceptance gates.

Requirements and tolerances come from the [normative physics model](../physics-model.md#9-numerical-and-visual-acceptance-gates).
The [data contracts](../contracts.md) define the public/private boundary and interval semantics.
The [machine-readable evidence](physics-summary.json) records the same measurements for later comparisons.

## Reproduce the Checks

From the repository root, install the committed dependency set and run the numerical suite:

```bash
uv sync --frozen
uv run pytest tests/physics -q -s
uv run ruff check backend/src/metis_sim/models backend/src/metis_sim/domain/physics.py tests/physics
uv run mypy backend/src/metis_sim/models backend/src/metis_sim/domain/physics.py
```

The initial recorded full-suite command was `uv run pytest tests/physics -q -s` (78 tests in 133.32 seconds).
After independent contract/immutability review, `uv run pytest tests/physics -q` passed all **80 tests in 112.45 seconds**, including the long 24-hour and six-hour reference checks.
Ruff passed and mypy reported no issues in the ten physics/domain source files.
After the full suite, an offline leap-table initialization guard was checked with `uv run pytest tests/physics/test_frames.py tests/physics/test_engine.py -m 'not slow' -q`: **7 passed, 1 deselected in 4.37 seconds**.
A subsequent provenance-only fix preserved the leap-table expiry's full UTC timestamp; `uv run pytest tests/physics/test_frames.py -q` then passed **4 tests in 4.14 seconds**.
Neither change altered orbital or EPS equations, and the long numerical suite was not repeated for those narrow changes.

The intentionally unsupported 2035 time fixture emits three ERFA “dubious year” warnings before the adapter rejects it.
Those warnings belong to a negative preflight test; the baseline uses covered 2026 inputs.

## Identify the Runtime and Inputs

| Item | Recorded value |
|---|---|
| Machine | Apple M3 Pro, 11 logical CPUs, 18 GiB RAM |
| Platform | macOS 26.6.2, arm64 |
| Python | CPython 3.12.12, Clang 21.1.4 |
| NumPy | 2.5.3 |
| Astropy | 8.0.1 |
| astropy-iers-data | 0.2026.9.21.0.56.25 |
| pyerfa | 2.0.1.5 |
| SciPy, reference integration/quadrature | 1.18.1 |
| pytest | 9.1.1 |
| Lockfile SHA-256 | `15d46334cbc36c1ac8bff6d97b4890b35e8a6c7ca5e070a395321d68272bc8e1` |

Installed versions were checked against [uv.lock](../../uv.lock).
Timing was measured during ordinary development on this host, with other work possible; it is not a controlled throughput benchmark.

The model constants are `mu=3.986004418e14 m³/s²`, `R=6378137 m`, and `J2=1.082629821313e-3`.
Production integration uses float64 RK4 with fixed 1-second steps.
Midpoint geometry uses cubic Hermite interpolation of adjacent RK4 positions and velocities, validated against the half-second trajectory.

The six-hour cases use [demo.yaml](../../configs/demo.yaml): epoch `2026-09-21T00:00:00Z`, duration 21,600 seconds, three satellites, seed 42, and no sensor noise.
The matched control is [healthy-matched.yaml](../../configs/healthy-matched.yaml).
The canonical normalized configuration hashes at this check were:

| Configuration | SHA-256 |
|---|---|
| Demo | `b884af19db02263cea411f24f9560417c6f21b0d2e36e2b3d6593defd6e81ec8` |
| Matched healthy | `7824d68aba83e773a435685e47ce0d724073ea54d402c50dfc65ab9e1c2613dd` |

### Verify Earth Orientation and Time Provenance

The adapter loads the lockfile-pinned package's `finals2000A.all` and `Leap_Second.dat`, disables network updates, verifies the entire run's table coverage before propagation, and rejects leap-second spans.
Elapsed SI seconds advance on TAI and are converted to UTC for samples.
The J2 axis is the terrestrial north-pole direction transformed to GCRS at the epoch and held fixed for the run.

| Input | Recorded provenance |
|---|---|
| IERS file SHA-256 | `d7adc96fca77e27746586e8b7dd75376eebbc82ba5f65ced13379cf0ebd62327` |
| IERS table coverage | MJD 41684 through 61666 |
| Baseline EOP status | Predicted values; disclosed, permitted by the specification |
| Leap-second file SHA-256 | `6cb6f5d4b819f2e568e25db4b0b26d89dedf031fdffb18bc94d40f4e94e268d7` |
| Leap-table expiry, UTC | `2027-06-27T23:59:23.000` |
| Inertial/public frame | GCRS / ITRS; public channel names retain `itrf` |

The expiry is Astropy's stored expiry instant converted to UTC; preserving the time avoids shortening it to the preceding calendar date.
Negative checks rejected the 2016 leap-second insertion, a 1970 run before EOP coverage, and a 2035 run beyond the leap-table expiry.

## Inspect the Numerical Gates

| Gate | Method and inputs | Required tolerance | Executed result |
|---|---|---|---|
| P-01 | 24-hour, J2=0, circular radius `R+550000 m`; compare every second against an independent trigonometric Kepler solution and specific two-body energy | Position ≤10 m; velocity ≤0.02 m/s; relative energy drift ≤1e-7 | Maximum position **2.31950947e-5 m**; velocity **2.52983954e-8 m/s**; energy drift **2.2144451e-14**. Passed. |
| P-02 | Three 24-hour J2 cases; compare 1 s RK4 to 0.5 s RK4 and independent SciPy DOP853; compare Hermite midpoints to the half-second trajectory | Maximum position difference ≤10 m | Maximum convergence difference **7.51957490e-5 m**; DOP853 difference **5.00153619e-5 m**; midpoint difference **7.51957392e-5 m**. Passed. |
| P-03 | 101 times across a UTC day boundary, independent analytic polar trajectory rotated away from coordinate axes; roundtrip GCRS/ITRS; centered differences at h=0.1 and 0.05 s | Roundtrip ≤0.01 m; velocity error ≤0.02 m/s | Roundtrip **2.87052896e-9 m**; velocity errors **1.60810509e-5** and **5.00133946e-6 m/s** respectively. Known ±90° longitude and an exact pole were also checked geodetically. Passed. |
| P-04 | Fixed SOFA-derived `t_c2t06a` matrix and nonsymmetric `[4000000,3000000,5000000] m` vector, through the production adapter's explicit time/EOP seam | Matrix element error ≤1e-12; position ≤0.01 m | Maximum matrix error **3.60822483e-15**; vector error **1.87425053e-8 m**. Passed. |
| P-05 | Five full-light/umbra/grazing disk geometries compared to independent SciPy area quadrature; eclipse entry compared to an independently solved angular-contact root | Fraction in [0,1], exact umbra generation zero; entry within 1 simulated second | All fractions within **1e-7** of quadrature; exact full-shadow power zero; coarse entry within **1 s** of the root. Passed. |
| P-06 | Sixty combinations of empty/near-empty/partial/near-full/full energy, generation/load pairs, zero/1/60 s windows and charge/discharge caps | Bus residual ≤1e-6 W; energy residual ≤1e-8 Wh plus float scale allowance | Maximum bus and load residuals **0 W**; maximum energy residual **3.99680289e-15 Wh**. Energy remained in [0,100 Wh]; no simultaneous charging/discharging. Passed. |
| P-07 | 100 W bus discharge for sixty 1-second steps, `eta_d=0.95`, initially 50 Wh | Energy decrease `100*60/(3600*0.95)` Wh within 1e-6 Wh | Measured loss **1.7543859649123306 Wh** vs analytic **1.7543859649122806 Wh**; error **4.99600361e-14 Wh**. Discharge sign positive. Passed. |
| P-08 | Identical 125-second physical trace at requested 20×, 1× and 5×, with a new satellite inserted earlier in ID order | Original physical/measurement values within 1e-9 relative/absolute | Existing satellite samples were **exactly equal** at all 126 ticks. This establishes engine speed/fleet independence; integrated pause/resume and persistence timing remain separate evidence. Partial gate. |
| P-10 | Four six-hour runs: affected baseline, exact healthy control, milder derating, and delayed onset | Healthy avoids outcome; baseline exhibits prior generation deficit and a state-driven outcome; variation changes outcome/censoring | Baseline confirmed at **20,650 s**, 60 s after reserve entry; other three runs had no reserve outcome within six hours. Details below. Passed at the engine boundary. |
| P-12 | Initial instant plus a mode change at tick 60, ramp knot at tick 120, and the battery boundary fixtures | No t=0 energy advance or divide by zero; correct endpoint/interval mode and midpoint segment | Initial energy **340 Wh** unchanged; frame 60 uses nominal **150 W** interval load with payload-active endpoint, frame 61 uses **210 W**; frame 120 endpoint derating **0.4**, interval midpoint **0.405**. Passed. |

Residual maxima for P-04/P-06/P-07 were read from the same fixed fixtures in a short numerical measurement after the full suite; the full-duration tests were not rerun for that readback.

### Reproduce the Independent Orbit Reference

The three P-02 inputs are osculating GCRS classical elements in metres/degrees:

| Case | a | e | i | RAAN | Argument of periapsis | True anomaly | RK4 1 s vs 0.5 s, max m | RK4 vs DOP853, max m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Circular equatorial | 6,928,137 | 0 | 0 | 0 | 0 | 33 | 7.51957490e-5 | 5.00153619e-5 |
| Near-polar | 6,928,137 | 0.001 | 97.6 | 17 | 21 | 123 | 3.69763158e-5 | 3.91283310e-5 |
| Eccentric retrograde | 7,078,137 | 0.05 | 179 | 53 | 89 | 231 | 2.83504844e-5 | 2.42581140e-5 |

Their common fixed symmetry axis is the normalized vector `[0.0026,0.00003,1]`.
The independent derivative is implemented separately in [test_orbit.py](../../tests/physics/test_orbit.py), with SciPy `solve_ivp(method="DOP853", rtol=2e-13, atol=1e-8)` and dense output compared at all 86,401 integer seconds.
The force equation is intentionally the same declared model; using another solver checks numerical propagation, not whether omitted physical forces are negligible for a real spacecraft.

The P-04 fixture is vendored with attribution in [sofa_c2t06a.json](../../tests/physics/fixtures/sofa_c2t06a.json).
It uses the normative pinned ERFA revision, two-part TT/UT1 JD `(2400000.5,53736.0)`, `xp=2.55060238e-7 rad`, and `yp=1.860359247e-6 rad`.
The expected matrix is fixed source data, not calculated through the production implementation.
This injection seam verifies the celestial/terrestrial matrix convention; P-03 independently exercises actual UTC/IERS lookup and rotating velocities.

## Verify Periodic Payload Operations

On 2026-09-26, the repeating schedule was checked on Apple M3 Pro, 18 GiB RAM,
macOS 26.6.2 ARM64, and Python 3.12.12.
An independent reviewer inspected recurrence expansion, overlap validation,
endpoint semantics, and the viewer's schedule-preservation path without finding
a correctness blocker.

A six-hour `SimulationEngine` run loaded `configs/telemetry-demo.yaml` through
`load_configuration`, removed its scenario for a fully supplied reference, and
summed `load_requested_w * sample_window_s / 3600` and
`load_served_w * sample_window_s / 3600` over METIS-02's completed active intervals.
Initialization took 31.11 seconds during concurrent local validation; this is
not a throughput benchmark.

| Active interval (simulated seconds) | Integrated active seconds | Requested load energy | Supplied load energy |
|---|---:|---:|---:|
| 3600–3900 | 300 | 17.5 Wh | 17.5 Wh |
| 9339–9639 | 300 | 17.5 Wh | 17.5 Wh |
| 15078–15378 | 300 | 17.5 Wh | 17.5 Wh |
| 20817–21117 | 300 | 17.5 Wh | 17.5 Wh |

At each start, endpoint `mode` was `payload_active` while `interval_mode` was
`nominal`; at each end these were `nominal` and `payload_active`, respectively.
The resolver retained `[9339,9639)` for a run ending at 9500, keeping its terminal
mode active. Configuration loading rejected a one-time safe interval at
9340–9350 that collided only with the second repetition, and rejected an
unsupported `repeat: daily` value. All four shipped configurations validated.

The existing six-hour counterfactual check also passed with the periodic schedule:

```bash
uv run pytest tests/physics/test_engine.py::test_full_six_hour_matched_control_and_varied_scenarios -q -s
```

| Run | First reserve entry | Confirmed outcome | Minimum SOC | Final SOC |
|---|---:|---:|---:|---:|
| Baseline | 20350 s | 20410 s | 0 | 0 |
| Matched healthy | None | None | 0.7530587307 | 0.8135359172 |
| Milder | None | None | 0.7529964916 | 0.8135034635 |
| Delayed | None | None | 0.2714094178 | 0.2714094178 |

These are engine results, not live deployment or persisted-run evidence.
The recurrence uses a fixed nominal period from initial semi-major axis, with
nearest-tick starts; it does not track J2 orbit crossings.
The fully supplied reference demonstrates 17.5 Wh per complete activation;
depleted runs still report unserved demand instead of manufacturing energy.
Existing stored configurations and runs retain their original schedules;
create a run from an updated configuration to use recurrence.

The focused existing contract, engine, scenario, viewer API, and Dart-contract
suite passed 46 checks with one Dart-dependent skip and one slow check deselected.
The slow comparison above passed separately; rerunning the Dart contracts with
`DART_EXECUTABLE=/tmp/metis-flutter/bin/dart` passed all five checks.
Ruff, mypy (55 source files), Flutter analysis, 18 existing Flutter checks,
the release web build, and the strict Zensical build passed.
No test files were added or edited.

The existing browser editor check
(`npm run test:e2e -- tests/browser/editor.spec.ts`) timed out looking for
`Edit constellation` directly on the overview; that action is now under Settings.
Its later assertion also still requires saving to clear every schedule.
A manual Playwright browser check against the release build followed
Settings → Edit constellation → Save as new run with mocked API responses;
the submitted METIS-02 operation retained `start_s: 3600`, `end_s: 3900`,
`mode: payload_active`, and `repeat: orbit`.
The legacy browser check needs updating before that automated gate can pass.
At that verification point the Dart format check also reported a pre-existing
multiline-format issue in `main.dart`'s custom-speed condition; formatting passed
after the dashboard follow-up below.

### Configure Tasks Through the Dashboard

The dashboard follow-up adds per-satellite payload controls described in
[Schedule Payload Operations](../frontend.md#schedule-payload-operations).
An independent review covered controller lifetime, satellite switching, preserved
non-payload operations, validation, save/refresh failures, and session expiry;
the reported save and dialog-lifetime findings were corrected and re-reviewed.

Manual Playwright verification used the release web build, the real local API,
and an isolated temporary SQLite database with a 10,000-second run.
For METIS-01, an orbit-repeating payload window at 1000–1300 seconds conflicted
on its second repetition with an existing safe-mode window at 6800–6860.
The API returned 422 with the overlap reason, and the editor retained its draft.
Changing the payload start to 2000 saved successfully (HTTP 200); an independent
configuration read returned both the safe window and the recurring 2000–2300
payload window. METIS-02's existing recurring and one-time payload operations
were preserved. No browser errors were reported in that flow.

Additional browser checks confirmed that disabling and re-enabling payload
scheduling retained an edited 420-second draft. A zero-duration task was caught
after switching to another satellite, with the editor returning to the satellite
containing the error. A newly added satellite saved a recurring 600–900-second
payload task; reopening the editor confirmed the persisted start, 300-second
duration, and enabled repeat setting.

`flutter analyze`, the 18 existing Flutter checks, the release web build, Dart
formatting for the four touched Dart files, and the strict documentation build
passed. `uv run pytest tests/integration/test_viewer_editing.py
tests/contracts/test_contracts.py -q` passed all 35 existing checks.
No test files were added or changed; the legacy browser check described above
still needs its navigation and old schedule-clearing expectation updated.
This is local verification, with no deployment or production database change.

## Inspect the Historical Six-Hour Causal Outcome

The measurements below are historical engine-boundary evidence from runs with a one-time METIS-02 payload interval from 3,600 through 3,900 seconds; they do not validate the current per-orbit recurrence contract.
All four historical runs preserve METIS-02's orbit, initial 340 Wh, 400 Wh capacity, mode schedule, and seed.
The nominal load is 150 W and the payload-active load is 210 W total.
Current recurrence rules are defined in [schedule payload operations](../physics-model.md#schedule-payload-operations).
The reserve is 15% SOC and requires 60 uninterrupted simulated seconds below that threshold.

| Run | Private generation change | First reserve entry | Confirmed outcome | Minimum SOC | Final SOC |
|---|---|---:|---:|---:|---:|
| Baseline | Linear multiplier 1→0.25 from 5,400 to 12,600 s | 20,590 s | 20,650 s | 0.0391526051 | 0.0391526051 |
| Matched healthy | Scenario removed | None | None | 0.7530592712 | 0.8266938120 |
| Milder | Same onset; final multiplier 0.85 | None | None | 0.7530592712 | 0.8266613583 |
| Delayed | Baseline ramp shifted later by 3,600 s | None | None | 0.3108831020 | 0.3108831020 |

The baseline enters reserve at `2026-09-21T05:43:10Z` and confirms the operational outcome at `05:44:10Z`.
The immediately preceding sample still has no confirmed failure time.
The healthy and baseline generation traces are exactly equal through tick 5,400 and have a positive integrated generation deficit before the baseline outcome.
All four orbit traces are exactly equal, so the power change does not move the satellite or manufacture unrelated geometry.

The other runs reach duration with no outcome and are eligible for right-censoring at the final committed sample.
Persisting the terminal censoring record belongs to the runner/repository and is not asserted by this engine-only comparison.
The baseline reserve violation is an operational energy outcome, not physical destruction or battery electrochemistry failure.

The first standalone three-satellite initialization took **18.92 seconds**.
The four comparison runs took **15.74–29.56 seconds each including initialization and reading all 21,601 target samples**.
Geometry and EPS are precomputed; subsequent sample reads perform no Astropy transforms.
These timings do not establish sustained frame delivery, memory limits, storage throughput, or the ten-satellite advertised speed tier.

## Preserve the Evidence Boundaries

This report does not validate P-09 Cesium interpolation/display timing, P-11 reconnect/stale/persistence behavior, the integrated pause/resume portion of P-08, or the ten-minute service/browser capacity gate.
Those checks require the runner, database, API, and actual browser together and must be reported separately.
Engine-level orbit previews match cached live endpoints and omit future EPS/private truth; that is not proof that every transport endpoint enforces the same projection.

The [frame tests](../../tests/physics/test_frames.py), [environment/EPS tests](../../tests/physics/test_environment_power.py), [scenario tests](../../tests/physics/test_scenarios.py), and [engine tests](../../tests/physics/test_engine.py) contain executable inputs and assertions.
The baseline has noise disabled; this evidence does not validate future sensor-noise generators or a learned health-warning model.

The physics model remains a six-hour synthetic short-arc approximation with a configured maximum of 24 hours and runtime altitude checks.
It omits drag, third-body forces, maneuvers, tides, radiation pressure, variable J2-axis motion, atmospheric/oblate-limb eclipse refinements, attitude actuator dynamics, and battery electrochemistry.
The selected near-polar inclination is not a verified Sun-synchronous orbit.
Predicted EOP values and the spherical eclipse approximation are disclosed rather than treated as exact Earth truth.
Numerical errors measured here are distinct from those physical-model omissions, and three P-02 fixtures do not exhaust every orbit in the supported configuration envelope.
