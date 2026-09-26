---
title: Physics Model and Visual Consistency
description: Define the orbit, time, environment, power model, progressive scenario, and numerical accuracy gates.
content-type: reference
audience: engineering and satellite operations
status: normative model and numerical gates
version: 1.0
date: 2026-09-21
---

# Physics Model and Visual Consistency

This is a normative appendix to the [specification](specification.md).
Equations and numeric tolerances below define the model and its acceptance gates. The [numerical validation report](validation/physics.md) records which checks the implemented simulator has passed and the limits of those results.

## 1. Define What Accurate Means

The viewer must show the state calculated by the backend at the displayed time.
The backend must solve a declared physical approximation rather than animate a circle or generate independent random measurements.
For fictional satellites, “correct position” means the solution of their configured initial-value problem within stated numerical tolerance.
It does not mean a known exact real-spacecraft position.

| Quantity | P0 model | Limit of claim |
|---|---|---|
| Orbit | Central Earth gravity plus J2 oblateness; Cartesian fixed-step RK4 integration | Short LEO arcs, no drag, third-body gravity, maneuvers, tides, or radiation pressure. |
| Frames/time | Explicit GCRS inertial state, Astropy Earth orientation to ITRS, UTC display | Accuracy depends on pinned Earth-orientation data; no silent fallback. |
| Sun | Astropy builtin Sun ephemeris in GCRS | Appropriate geometric illumination reference; not a solar weather forecast. |
| Eclipse | Spherical occulting Earth and finite solar disk overlap | Umbra/penumbra included; no atmosphere/refraction or oblate-limb eclipse refinement. |
| Attitude/panel | Prescribed LVLH body frame and ideal two-axis Sun tracking equivalent panel | Kinematic prescription, no pointing control dynamics, gimbal limits, or actuator energy. |
| Electrical power | Bus-level generation/load allocation plus bounded energy store and efficiencies | No battery electrochemistry, voltage sag, MPPT transient, current/ripple, or cell-level faults. |
| Telemetry | Configured sensor sampling/noise after physics, ideal SOC estimator disclosed | Noise is synthetic; no real-mission calibration claimed. |

This model is suitable for a six-hour scenario and at most a 24-hour configured run within a supported LEO envelope: osculating perigee altitude at initialization at least 300 km, apogee at most 1,500 km, eccentricity at most 0.05, inclination from 0° through 180°.
The altitude validation for orbital elements uses radius above the configured equatorial radius; reported geodetic altitude is a different quantity.
Earth intersection or departure from the supported runtime envelope fails the run with a diagnostic; do not silently clamp the orbit.
J2 makes near-polar precession possible, but an arbitrary 97° inclination must not be advertised as a verified Sun-synchronous orbit.

The user's “solar cycle” requirement is interpreted as the orbital sunlight/eclipse energy cycle.
The eleven-year solar activity cycle and geomagnetic disturbances are separate future models.

## 2. Time and Reference Frames

**PHY-02:** Store an epoch in UTC, elapsed SI seconds on an integer tick, and use Astropy time-scale conversion for physical calculations.
Advance elapsed time on a continuous TAI timeline and convert to UTC for interchange.
P0 rejects a run spanning a leap-second insertion because the browser/JSON time contract does not support a `:60` second; the backend must detect this using its pinned leap-second table.
Speed changes affect wall-clock pacing only.

Frame names are never just `ECI` or `ECEF` without a defined convention:

- Integration state: Earth-centered GCRS Cartesian position in metres and velocity in metres per second, at each sample's epoch.
- Public rendering state: ITRS Earth-fixed coordinates, exposed under `*_itrf_*` channel names as the P0 realization of that terrestrial frame. The descriptor states `frame=ITRS`, pinned Earth-orientation inputs, and no survey-grade realization claim.
- Geographic readout: WGS84 geodetic latitude, east-positive longitude, and ellipsoidal height.
- Body attitude in the optional `spacecraft.v1` extension: Hamilton quaternion `[w,x,y,z]`, scalar first, actively mapping body vectors into GCRS at the stated epoch. This supersedes the earlier proposed future ITRS/xyzw convention; rendering must explicitly convert frames/order rather than infer Cesium compatibility.

Convert state and velocity together using the frame transformation's differential support.
Rotating velocity components alone misses the rotating-frame term and is incorrect.
The frontend must not reinterpret inertial vectors as Earth-fixed coordinates or rotate already Earth-fixed data again.
Astropy documents time-tagged satellite state conversion, including TEME to ITRS for a future SGP4 adapter. [Astropy satellite coordinates](https://docs.astropy.org/en/stable/coordinates/satellites.html)

Pin Python/library versions, `astropy-iers-data`, the exact IERS table/checksum, and leap-second inputs for each run.
Disable opportunistic network updates during a run.
Before start, verify the entire interval is covered and record whether Earth-orientation values are observed or predicted; predicted table entries are permitted with disclosed provenance.
Out-of-coverage/degraded Earth-orientation calculations must fail validation rather than quietly approximate a UTC rotation.
IERS values supply UT1–UTC and polar motion for these transformations. [Astropy IERS documentation](https://docs.astropy.org/en/stable/utils/iers.html)

## 3. Propagate Configured Orbits

**PHY-03:** P0 supports `j2_cartesian` initialized from osculating classical elements at the run epoch: semi-major axis `a`, eccentricity `e`, inclination `i`, right ascension of ascending node `Ω`, argument of periapsis `ω`, and true anomaly `ν`.
Angles are degrees in configuration and radians inside the model.
Classical elements reference the GCRS X/Y plane and +X direction.
Circular/equatorial singular elements are accepted only under a documented canonical convention (`ω=0` for circular, `Ω=0` for equatorial), while Cartesian state remains nonsingular.
The implementation must normalize equivalent element representations deterministically.

Use documented constants fixed by `earth_model=wgs84_j2_v1`:

```text
mu = 3.986004418e14 m^3/s^2
R  = 6378137.0 m
J2 = 1.082629821313e-3
```

These are the WGS84 Earth-model values selected for the model, not tunable per-satellite parameters. [NGA WGS84 reference](https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84)

To avoid treating an unspecified inertial +Z as the current Earth pole, obtain the terrestrial +Z unit vector expressed in GCRS at the run epoch using the pinned transform.
Hold this symmetry axis `p` fixed over the short run; its neglected time variation is an explicit model approximation.
For `r` the position vector, `rho = |r|`, `z = r·p`, and `s=z/rho`:

```text
dr/dt = v
dv/dt = -mu * r / rho^3
        + (3/2) * J2 * mu * R^2 / rho^5
          * ((5*s^2 - 1) * r - 2*z*p)
```

Initialize position and velocity from the two-body osculating elements, then propagate this force model using float64 RK4 with a fixed 1 s step.
The same force model is used by live state and orbit preview; previews must be computed from the original orbit state or a consistent cached integration, never mutate the live runner.
Orbit can be precomputed for the configured interval and shared read-only with runner/viewer because P0 has no maneuvers or force-changing faults.
Batch time/frame conversion across satellites and cache common environment inputs before introducing multiprocessing.

For the two-body test mode only (`J2=0`), the reference period is `T=2*pi*sqrt(a^3/mu)`; a 550 km circular-radius reference orbit is about 95.65 minutes.
The orbit recurrence schedule also uses this two-body period as a fixed nominal cadence while physical propagation retains J2; it does not represent J2-adjusted orbit crossings. See [schedule payload operations](#schedule-payload-operations).
Do not enforce exact Kepler energy conservation with J2 enabled; validate the corresponding conservative potential or compare against an independent integration of the same force model.

**Why not SGP4 first:** synthetic osculating elements are easy to configure; they are not TLE mean elements.
SGP4 is the right optional adapter for imported TLE/GP data, whose epoch, native TEME frame, propagation errors, and source age must be preserved.
Do not fabricate a TLE from arbitrary osculating elements and imply equivalent dynamics.
TLE predictions also do not guarantee real-spacecraft position accuracy. [CelesTrak SGP4 reference](https://celestrak.org/publications/AIAA/2006-6753/), [Skyfield satellite limitations](https://rhodesmill.org/skyfield/earth-satellites.html)

## 4. Compute Illumination and Panel Incidence

**PHY-04:** Compute the Sun position with Astropy `get_sun(t)` in GCRS, subtract the satellite position, and normalize to obtain satellite-to-Sun direction `u` and distance `d`.
Use the same time and coordinate frame for all dot products.
The builtin ephemeris avoids a required runtime kernel download; record the Astropy/ERFA versions in the manifest. [Astropy get_sun](https://docs.astropy.org/en/stable/api/astropy.coordinates.get_sun.html)

For a spherical Earth of radius `R` and solar radius `R_sun=695700000 m`, viewed from the satellite:

```text
alpha = asin(R / |r_sat|)                  # Earth's angular radius
beta  = asin(R_sun / |r_sun - r_sat|)      # Sun's angular radius
theta = acos(clamp((-r_sat/|r_sat|) dot u, -1, 1))
```

If the disks are separated (`theta >= alpha+beta`), illumination is 1.
If Earth fully covers the solar disk (`alpha >= theta+beta`), illumination is 0.
For partial overlap, calculate the standard two-circle overlap area in angular-radius coordinates and set `illumination = 1 - overlap/(pi*beta^2)`, clamped to `[0,1]` for numerical roundoff only.
Handle coincident centers/containment explicitly before divisions and `acos`.
This angular-disk approximation is the chosen penumbra model; validation includes known full-light/full-shadow cases and a reference implementation of the same geometry.
Spherical Earth means a small terminator discrepancy relative to Cesium's WGS84 globe is possible and must be described as model approximation rather than hidden.
Basilisk also models partial occultation and shadow fraction and can be used as an independent reference after aligning radii/ephemeris. [Basilisk eclipse](https://avslab.github.io/basilisk/Documentation/simulation/environment/eclipse/eclipse.html)

Panel orientation is explicitly prescribed.
For the LVLH body frame choose `+Z` toward Earth, `+Y` opposite the orbit angular momentum, and `+X = +Y × +Z` (along-track for a circular prograde orbit).
P0 allows `panel_pointing.type=ideal_sun_tracking` only: a virtual two-axis equivalent array sets its normal to `u` so its incidence cosine is 1; Earth shadow still gates generation.
This is an explicit ideal actuator assumption, not a solved ADCS system.
The equivalent area represents the aggregate array, not the physical body silhouette.
Preserve the incidence calculation `max(0,n·u)` so P1 can add body-fixed or one-axis array policies without rewriting EPS.

The P0 power source equation is:

```text
solar_bus_w = irradiance_1au_w_m2 * (AU_m / d)^2
              * area_m2 * efficiency * conversion_efficiency
              * max(0, panel_normal dot u) * illumination * hidden_derating
```

Set `AU_m=149597870700` and baseline irradiance `1361 W/m²` as fixed model inputs.
The Sun-distance term varies across the year; P0 does not add weather-driven variability.
Electrical load never directly changes solar illumination.
Hidden derating is held at 1 in healthy runs and modified only by the private scenario.

## 5. Balance Power and Integrate Battery Energy

**EPS-02:** Battery state is stored energy `E` in Wh, bounded by fixed usable capacity `C`.
SOC is `E/C`; percentages appear only as a UI formatting choice.
P0 has no capacity-changing degradation, avoiding ambiguous SOC denominator changes or disappearing energy.
Do not manufacture battery voltage/current channels from arbitrary curves; add them later only with a declared circuit model.

Let `G` be generated bus power, `L` requested load, `dt_h=dt_s/3600`, `eta_c` charging efficiency, and `eta_d` discharge efficiency.
All bus powers below are nonnegative except signed `battery_power_w`.

```text
If G >= L:
    charge_w = min(G-L, max_charge_w, (C-E)/(eta_c*dt_h))
    discharge_w = 0
    served_w = L
    curtailed_w = G-L-charge_w
    unserved_w = 0
Else:
    discharge_w = min(L-G, max_discharge_w, E*eta_d/dt_h)
    charge_w = 0
    served_w = G+discharge_w
    unserved_w = L-served_w
    curtailed_w = 0

battery_power_w = discharge_w-charge_w
E_next = E + eta_c*charge_w*dt_h - discharge_w*dt_h/eta_d
```

Use midpoint illumination/generation for interval energy integration; split an interval at the battery full/empty boundary if necessary or use the above energy-limited average power consistently.
The outputs `charge_w`, `discharge_w`, `served_w`, `curtailed_w`, and `unserved_w` represent the interval-average power over `(t-dt,t]` when stamped at endpoint `t`; `solar_power_w` and `load_requested_w` use the same interval-average convention.
The frame's required `interval_mode` identifies the operational mode used for these powers; top-level `mode` identifies the endpoint mode.

Position, illumination, incidence, mode, SOC, and battery energy are endpoint states at `t`; the catalog must disclose this distinction.
At t=0, publish initial state and instantaneous power allocation with no energy advancement, marked `sample_window_s=0` in the frame; all subsequent P0 frames use `sample_window_s=1`.
For this sequence-zero branch, do not call a formula that divides by `dt_h`: use `charge_w=min(G-L,max_charge_w)` only when `G>=L` and `E<C`, otherwise zero; use `discharge_w=min(L-G,max_discharge_w)` only when `G<L` and `E>0`, otherwise zero.
Calculate served/curtailed/unserved power from those allocations, retain `E_next=E`, and evaluate initial limit state without advancing a dwell timer.

For each interval `[t_k,t_k+1]`, use the operational mode effective at `t_k` throughout its interior and evaluate the piecewise-linear derating function at its midpoint for generation.
Propagate orbit, evaluate midpoint environment, and integrate energy using those interval inputs.
At `t_k+1`, first finalize energy, then apply any operation becoming effective there, evaluate endpoint environment/outcomes, and emit endpoint events and the measurement frame.
At an operational boundary, an event records the exact effective tick and the new mode; the completed interval's power remains associated with its preceding mode through its sample window.
Sequence zero applies operations effective at zero before initial sampling.
Midpoint orbit state must come from the same integrator trajectory (a validated dense interpolation or half-step evaluation), not from an unrelated straight-line orbital model.

The two mandatory balances, before noise, are:

```text
G + battery_power_w = served_w + curtailed_w
L = served_w + unserved_w
E_next-E = eta_c*charge_w*dt_h - discharge_w*dt_h/eta_d
```

Do not simply clamp SOC after integrating unlimited demand; that destroys the energy accounting and hides unmet loads.
The physical battery model continues after a reserve violation so later unserved-power consequences remain observable.

`nominal` and `payload_active` select configured load totals; `safe` selects a reduced total.
Sunlight/eclipse is an environment state, not an exclusive operational mode: a satellite can operate its payload while in eclipse if scheduled.
P0 schedules may command safe mode at a configured tick, but there is no automatic low-SOC safe-mode protection by default.
If P1 adds autonomous protection, its thresholds, delay/hysteresis, and priority must be explicit and evaluations must distinguish protected from unprotected runs.

### Schedule Payload Operations

An operation's `start_s` and `end_s` define its first half-open interval `[start_s,end_s)`. `repeat` is optional and defaults to `null`, which means the operation occurs once. P0 also accepts `repeat: orbit`, which repeats the same operation at a fixed nominal two-body cadence derived from that satellite's initial semi-major axis:

```text
T = 2*pi*sqrt(a_m^3 / MU)
MU = 3.986004418e14 m^3/s^2
start_n = start_s + round(n*T), n = 0, 1, 2, ...
end_n = start_n + (end_s - start_s)
```

`round` uses Python's nearest-integer, ties-to-even behavior.
This recurrence is anchored to the first declared start; it does not track J2-adjusted orbital crossings or phase.
For `a_m=6928137`, `T` is approximately `5738.993 s`.
Every operation's first declared interval must fit within the run.
Recurring windows whose starts are at or before the run end are considered; integration stops at the configured duration, so its last window can be partial.
If that window extends beyond the run, the endpoint mode remains active.
Reject any overlaps between declared or generated operation intervals, including overlaps between recurring operations.
Outside active windows, use `initial_mode`.

The demonstration schedules METIS-02 for a 300-second payload-active interval beginning at 3600 seconds on every nominal orbit.
The payload-active `210 W` is the total spacecraft load; nominal and safe modes use `150 W` and `70 W` totals, respectively.
A fully supplied 300-second activation consumes `17.5 Wh` of total spacecraft load, of which `5 Wh` is additional to nominal operation.
Battery energy change also depends on solar generation during the interval and charge/discharge efficiency.

## 6. Define the First Fault Outcome

**FLT-03:** `solar_derating` applies a piecewise-linear multiplier in `[0,1]` to available generation.
Time is elapsed simulated seconds from run start, never wall time, browser time, or an unstable “current orbit count.”
Before the first point, use 1; after the final point, hold its last value.
Point times are increasing and align to ticks.

For the baseline, “failure” means **stored energy remains below the configured operational reserve for 60 continuous simulated seconds**.
It is an operational energy-reserve violation, not destruction of the satellite or proof of physical battery failure.
Record the first threshold entry separately from the confirmed failure time.
Evaluate endpoint samples: begin the timer on the first endpoint with `SOC < reserve_soc`; clear it when `SOC >= reserve_soc`; confirm at `entry_time + 60 s` if still below.
The health signal has therefore preceded this outcome by at least the configured dwell, but this alone is not evidence of a useful ML warning.
The reserve threshold/dwell used for private evaluation are stored in truth; public configured limit events, if enabled, must use explicitly public limit definitions.

A healthy matched run uses exactly the affected satellite's orbit, initial energy, load schedule, and seed with derating disabled.
The other two satellites are visual fleet context, not automatically valid experimental controls if their orbital phases differ.
For generalization, later analytics must split by complete runs/scenarios/satellites and use multiple seeds, severities, starts, and no-failure runs; random splits of overlapping time windows invite leakage.

## 7. Baseline Configuration Example

This is the original complete configuration example used to define the format. The executable, calibrated fixture is [configs/demo.yaml](../configs/demo.yaml); schema validation and healthy/fault outcome results are recorded in [implementation validation](validation/README.md).
The example uses distinct orbital phases in one plane; it does not claim an operational constellation design.

```yaml
schema_version: simulation.v1
run:
  epoch_utc: "2026-09-21T00:00:00Z"
  duration_s: 21600
  tick_s: 1
  telemetry_period_s: 1
  speed: 20
  seed: 42
  earth_model: wgs84_j2_v1
  orbit_model: j2_cartesian
  sun_model: astropy_builtin
profiles:
  leo_power_demo:
    panel:
      area_m2: 0.9
      efficiency: 0.28
      conversion_efficiency: 0.95
      irradiance_1au_w_m2: 1361.0
      pointing: {type: ideal_sun_tracking}
    battery:
      type: energy_store
      usable_capacity_wh: 400.0
      initial_soc: 0.85
      charge_efficiency: 0.95
      discharge_efficiency: 0.95
      max_charge_w: 250.0
      max_discharge_w: 300.0
    loads_w:
      nominal: 150.0
      payload_active: 210.0
      safe: 70.0
    sensors:
      catalog: power-leo.v1
      noise: {type: none}
satellites:
  - satellite_id: METIS-01
    name: Metis One
    profile_id: leo_power_demo
    orbit: {a_m: 6928137.0, e: 0.001, i_deg: 97.6, raan_deg: 0.0, argp_deg: 0.0, true_anomaly_deg: 0.0}
    initial_mode: nominal
    operations: []
    visual: {color: "#8FD3FF", asset_id: null}
  - satellite_id: METIS-02
    name: Metis Two
    profile_id: leo_power_demo
    orbit: {a_m: 6928137.0, e: 0.001, i_deg: 97.6, raan_deg: 0.0, argp_deg: 0.0, true_anomaly_deg: 120.0}
    initial_mode: nominal
    operations: [{start_s: 3600, end_s: 3900, mode: payload_active, repeat: orbit}]
    visual: {color: "#F7C873", asset_id: null}
  - satellite_id: METIS-03
    name: Metis Three
    profile_id: leo_power_demo
    orbit: {a_m: 6928137.0, e: 0.001, i_deg: 97.6, raan_deg: 0.0, argp_deg: 0.0, true_anomaly_deg: 240.0}
    initial_mode: nominal
    operations: []
    visual: {color: "#A8E6B5", asset_id: null}
constellations:
  - constellation_id: metis-demo
    satellite_ids: [METIS-01, METIS-02, METIS-03]
scenario:
  - satellite_id: METIS-02
    type: solar_derating
    points:
      - {at_s: 5400, multiplier: 1.0}
      - {at_s: 12600, multiplier: 0.25}
    outcome: {type: energy_reserve_violation, reserve_soc: 0.15, dwell_s: 60}
```

Schedule intervals are `[start_s,end_s)` and revert to `initial_mode` when no interval is active.
The example fault increases gradually over two hours and thereafter holds 25% generation; its exact reserve-crossing time is deliberately unspecified until execution proves it.
At 20× a six-hour run takes about 18 wall minutes if throughput meets target.
For a five-minute P0 presentation, prepare a run in advance, pause at a suitable committed point late in its progression, then open the current snapshot and resume at 20×.
This uses existing controls; recorded-run playback/seek remains P1.
A full six-hour story in five minutes would require 72×, which P0 does not promise.

## 8. Visualize the Authoritative State

**VIS-02:** Use Flutter/Dart for the web application and CesiumJS through a rendering-only HTML platform view.
Cesium provides geospatial ellipsoid/camera/time primitives and sampled time-varying positions, which reduces custom coordinate and globe work. [Cesium SampledPositionProperty](https://cesium.com/learn/cesiumjs/ref-doc/SampledPositionProperty.html)

Provide ITRS positions in metres as `ReferenceFrame.FIXED`, time-tagged with the backend's UTC, using cubic Hermite interpolation with the corresponding ITRS velocity samples.
Keep the display time within the available sample bracket.
Do not extrapolate when a connection stalls.
Use bounded committed playback lag (target at most 0.5 wall seconds at 20×) to obtain adjacent samples, disclose the lag, and freeze with a stale indicator when data stops.
The selection panel uses the nearest prior committed health frame to that display time and prints its actual timestamp; frame cadence bounds its difference to at most one simulated second.
On pause, drain to the acknowledged committed endpoint and freeze both view and readings.

Drive Cesium's time explicitly from backend clock state plus monotonic elapsed wall time, clamped to committed samples; disable independent free-running timeline controls in live mode.
Cesium's `Clock` has separate current time, multiplier, and animation behavior; the implementation must synchronize all three. [Cesium Clock](https://cesium.com/learn/cesiumjs/ref-doc/Clock.html)
Display “Simulation UTC,” requested speed, effective speed, run state, and stale/lag state in the viewer.
The wall time belongs in diagnostic metadata, not the globe's date readout.

P0 offers an Earth-fixed camera for surface context and an optional inertial camera mode for seeing Earth rotate under the orbit.
In Earth-fixed mode the globe need not visibly spin; Earth rotation is already accounted for in the terrestrial coordinates.
Never artificially spin Earth in an Earth-fixed scene while feeding Earth-fixed positions.
Orbit trails and preview paths must use time-tagged backend samples, since a future ground-relative trajectory does not form a closed fixed ellipse.

The scene must support mouse/touchpad zoom, rotate/pan, satellite selection, reset-to-Earth, and follow-selected satellite.
Provide a keyboard-accessible satellite list and textual power/state panel, so the 3D canvas is not the sole interaction path.
Use a visually enlarged marker with a “symbolic size” label; maintain Earth/orbit positional scale.
Hide or de-emphasize satellites occluded by Earth.
No faulty-component highlighting is required in P0.

P0 uses an offline local Earth imagery asset with clear attribution, or an untextured WGS84 globe if no suitable asset is bundled.
Do not require Cesium ion, paid terrain, access tokens, or external imagery to run the demo.
Pin Flutter and Cesium versions and the local asset-copy configuration and test on the actual demo browser.
Configure day/night lighting from the backend Sun vector transformed to ITRS, or explicitly label Cesium's visual lighting as approximate; backend shadow fraction always owns the EPS calculation.

Future 3D assets attach via `asset_id` resolved by an allowlisted catalog; scale/orientation corrections belong to the asset descriptor.
An unavailable asset falls back to the marker without breaking simulation.
A later body quaternion and component metadata can enable model rotation and highlighting; neither the GLB geometry nor a clicked component defines physical truth automatically.

## 9. Numerical and Visual Acceptance Gates

These gates validate implementation consistency with this model, not flight accuracy.
Record inputs, software/data versions, reference method, numeric results, and limits in the resulting validation report.

| ID | Setup | Pass condition |
|---|---|---|
| P-01 | J2=0 circular 550 km reference; integrate 24 h | Against independent analytic two-body solution: position error ≤10 m, speed error ≤0.02 m/s; relative specific-energy drift ≤1e-7. |
| P-02 | Same J2 configuration at dt=1 s vs 0.5 s and independent adaptive high-accuracy integrator | Maximum position difference ≤10 m over 24 h for supported fixture orbits; record errors separately from omitted-force uncertainty. |
| P-03 | At least 100 times/positions including poles, dateline, day boundary | GCRS→ITRS→GCRS round trip position error ≤0.01 m; terrestrial velocity agrees with centered finite difference `(r_ITRS(t+h)-r_ITRS(t-h))/(2h)` for `h=0.1 s` to ≤0.02 m/s, using independent dense orbital positions at each time. Repeat at `h=0.05 s` to check convergence. |
| P-04 | Published SOFA `t_c2t06a` celestial-to-terrestrial matrix fixture with its stated TT, UT1 and polar motion inputs, plus a nonsymmetric test vector | Use the fixed expected matrix from that source rather than recompute expected output through the production adapter; matrix entries agree to 1e-12, then transform a 7,000 km-scale vector with ≤0.01 m position error. Round trip alone is insufficient. |
| P-05 | Full-sun, anti-Sun umbra, grazing overlap geometries | Illumination in `[0,1]`; exact full-shadow generation zero before noise; transition time agrees with a finer-step reference within 1 simulated second under identical geometry. |
| P-06 | Noiseless power for full/empty batteries, charge/discharge caps, excess generation, unmet load | Per-step bus balance residual ≤1e-6 W; energy residual ≤1e-8 Wh plus floating-point scale allowance; no energy creation through clipping. |
| P-07 | Constant 100 W bus discharge, eta_d=0.95, 60 s, sufficient energy | Energy decreases by `100*60/(3600*0.95)` Wh within 1e-6 Wh; sign matches catalog. |
| P-08 | Identical run at 1×/5×/20× with pause/resume and another satellite added | Same original satellites' noiseless state within 1e-9 relative/1e-9 absolute numerical tolerance; identical seeded measurements in the same locked environment, excluding run/stream IDs and wall metadata. |
| P-09 | Cesium evaluated at stored times and intermediate times | At sample times, Cartesian position error ≤0.01 m; interpolation against backend dense reference ≤100 m; displayed health timestamp lag ≤1 simulated second. |
| P-10 | Healthy and derated matched runs plus varied onset/severity | Healthy baseline avoids failure; affected baseline has a measurable pre-failure generation deficit and state-triggered reserve outcome; changing severity changes outcome or yields censoring. |
| P-11 | Pause, reconnect, slowed DB, resumed consumer | No simulated time jumps or hidden dropped frames; stale UI freezes; replay recovers retained measurements by identity. |
| P-12 | t=0 empty/full/part-full battery, a load step at t=60, and a derating control point at t=120 | No division by zero; initial energy unchanged; frame 60 carries old interval-average load/interval_mode and new endpoint mode, frame 61 carries the new load; fault ramp uses the correct midpoint segment without a one-tick phase shift. |

Power/geometry numerical gates operate before optional noise.
Unit and frame tests should include known nonzero longitude and non-equatorial states; a single equatorial x-axis fixture can conceal a frame error.
SOFA publishes validation programs and celestial/terrestrial transformation routines; vendor the selected fixture with its release identity and attribution during implementation. [SOFA tools and validation](https://www.iausofa.org/about-us), [SOFA release test-program reference](https://www.iausofa.org/changes)
For P-04 the fixed source is the SOFA-derived ERFA `t_c2t06a` fixture at commit `1a8044cde5b7763295d472a6443387239127c6c8` (routine revision 2013-08-07).
Use two-part TT JD `(2400000.5,53736.0)`, two-part UT1 JD `(2400000.5,53736.0)`, `xp=2.55060238e-7 rad`, and `yp=1.860359247e-6 rad` with the expected matrix below.
These are synthetic validation inputs supplied directly, not an assertion that TT and UT1 were physically equal on that date; no network IERS lookup participates in this fixture. [Pinned ERFA validation source](https://github.com/liberfa/erfa/blob/1a8044cde5b7763295d472a6443387239127c6c8/src/t_erfa_c.c)

```text
expected celestial-to-terrestrial matrix:
[-0.1810332128305897282,  0.9834769806938592296,  0.00006555550962998436505]
[-0.9834768134136214897, -0.1810332203649130832,  0.0005749800844905594110 ]
[ 0.0005773474024748545878, 0.00003961816829632690581, 0.9999998325501747785]
test input position (m): [4000000, 3000000, 5000000]
```

Inject these time/EOP inputs through the production coordinate adapter and compare against the fixed matrix acting on the test vector; do not only call ERFA's own self-test.
P-03 separately checks the production UTC/IERS path and velocities; the matrix fixture alone does not validate timestamp parsing or rotating velocity terms.
If a gate fails, fix the model or reduce the supported envelope explicitly; do not widen tolerances without documented numerical evidence.

## 10. Optional Physical Housekeeping Models

The subsequent `spacecraft.v1` extension adds declared models around the existing conserved orbit/EPS ledger; the historical P0 fidelity table above describes `power-leo.v1`.
Its [model reference](reference/spacecraft-telemetry.md#interpret-the-physical-models) records exact equations, units, and limits, and [telemetry configuration](../configs/telemetry-demo.yaml) provides an explicit opt-in example.
No supplied CSV values enter simulation or substitute for a physical model.

Ideal regulated rails derive charge/discharge terminal currents using the existing efficiencies and `I=P/V`; converter losses enter a three-node battery/avionics/payload heat ledger.
One-second forward Euler combines electrical heat, distance/eclipse-dependent direct solar absorption, symmetric conduction, and Stefan–Boltzmann radiation.
There is no electrochemical voltage curve, thermal feedback into EPS, Earth IR/albedo, thermostat, or heater model; temperatures outside 100–500 K fail instead of being clamped.
Payload power is a portion of served mode load, with acquisition gated on full supply and available storage; counters advance only on completed simulated intervals.

Ideal LVLH body axes are `+Z=-r_hat`, `+Y=-h_hat`, and `+X=+Y×+Z`; target attitude equals actual attitude by prescription.
Quaternion output uses the body-to-GCRS wxyz convention above; analytic axis derivatives produce angular rate, and a centered axial dipole produces the body magnetic vector.
The independent equivalent solar array remains ideally Sun tracking, as if freely gimbaled, rather than fixed to that nadir body.
Actuator/wheel/control dynamics and mission sensor calibration remain absent; unsupported quantities are explicitly missing.
The solar-derating scenario can change electrical/thermal behavior and power available to a scheduled payload, but does not introduce an attitude failure, thermal-aging model, or predictor.
