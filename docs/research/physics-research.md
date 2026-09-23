# Orbit, visualization, eclipse, and power fidelity research

Status: engineering recommendation for the simulator specification. This is not an implementation report and none of the proposed scenario outcomes below has been executed yet.

## Decision

Use one mandatory P0 physics path for all synthetic satellites:

1. A backend-owned, integer-tick simulation clock advances by a fixed 1 simulated second.
2. Convert configured classical elements to a Cartesian state at the scenario epoch.
3. Propagate that state with deterministic fixed-step RK4 using central Earth gravity plus the J2 perturbation.
4. Use Astropy for UTC/TAI handling, Sun direction, and the GCRS-to-ITRS/ECEF transformation.
5. Compute eclipse, prescribed attitude, solar incidence, generated power, loads, and battery energy in the backend.
6. Send time-tagged ECEF positions and velocities to Cesium. Cesium interpolates and renders them but never advances the authoritative simulation.

This is the lowest-risk route for configurable fictional satellites. It is materially better than drawing a circular orbit, but remains small enough to inspect and test. It also leaves a clean `OrbitPropagator` boundary for a later SGP4/TLE adapter or Basilisk adapter.

The P0 target is three configured satellites, with the same code path supporting 1–10 satellites. Default output is 1 telemetry sample per simulated second and the demo default is 20x wall-clock speed. Speed changes how many fixed ticks are executed per wall-clock interval; it does not change the physics step.

## Why this path

| Choice | Strong fit | Material limitation | Decision |
|---|---|---|---|
| Synthetic Cartesian RK4, central gravity + J2 | Arbitrary fictional spacecraft; simple YAML inputs; deterministic replay; no TLE fabrication; enough fidelity for several LEO orbits | Omits drag, higher harmonics, third bodies, maneuvers, and orbit determination | Mandatory P0 path |
| SGP4 with TLE/OMM | Correct model family for public catalog elements; very fast; standard validation vectors | TLE fields are model-specific mean elements, not generic Kepler elements; output is TEME; accuracy degrades away from the element epoch | Optional adapter after P0 |
| Basilisk | Ready-made modular spacecraft dynamics, conical eclipse, incidence-aware solar panels, batteries, attitude, and reaction-wheel power | Adds its own scheduling/message graph and a broad simulation framework to the service integration path | Validation oracle and later high-fidelity generator, not a P0 runtime dependency |

The SGP4/TLE boundary is important. The reference SGP4 work describes TLE propagation as modestly accurate and fast, with TEME position/velocity output. It also reports that TLE accuracy is generally about a kilometer at epoch and degrades quickly; a TLE does not carry its own uncertainty. Therefore, a UI must not present an SGP4 track as precision orbit determination. See the [CelesTrak SGP4 reference implementation and tests](https://celestrak.org/publications/AIAA/2006-6753/), [SGP4 orbit-determination paper](https://celestrak.org/publications/AIAA/2008-6770/), and [TLE accuracy validation](https://celestrak.org/publications/AAS/07-127/).

Basilisk remains a strong second-stage option. Its current project supplies Python interfaces over simulation modules and prebuilt installation paths. Its power example already joins orbit and attitude, eclipse, a solar panel, loads, and battery storage. Its panel model uses eclipse factor, efficiency, panel area, and the panel-normal/Sun-direction cosine; its eclipse module supplies a continuous shadow factor for umbra and penumbra. See the [Basilisk repository](https://github.com/AVSLab/basilisk), [simulation fundamentals](https://avslab.github.io/basilisk/Learn/bskPrinciples.html), [solar-panel model](https://avslab.github.io/basilisk/Documentation/simulation/power/simpleSolarPanel/simpleSolarPanel.html), [eclipse model](https://avslab.github.io/basilisk/Documentation/simulation/environment/eclipse/eclipse.html), and [reaction-wheel power example](https://avslab.github.io/basilisk/examples/scenarioAttitudeFeedbackRWPower.html).

## Authoritative time and frame contract

Avoid the words `ECI` and `ECEF` without a named frame in code or a contract.

### Simulation time

- Scenario input: `epoch_utc`, an RFC 3339 UTC instant with `Z`.
- Authoritative state: `(epoch, tick_index, fixed_dt_seconds)`. Derive a sample time from the integer tick; never accumulate browser frame deltas.
- Internal arithmetic: Astropy `Time`; advance elapsed SI seconds on a monotonic scale and serialize output as UTC.
- Output: both `timestamp_utc` and `elapsed_sim_s` on every state and telemetry sample.
- Pause, resume, replay, and speed changes cannot change the sequence of simulated timestamps or states.
- Package a pinned `astropy-iers-data` version for the scenario epoch. Do not silently accept degraded Earth-orientation data. Record the data version in run metadata.

Astropy documents that precise Earth rotation and coordinate transforms depend on IERS data, and that automatic tables can change as new measurements arrive. A pinned table makes a demo replayable; a production mode can refresh it deliberately. See [Astropy IERS data access](https://docs.astropy.org/en/stable/utils/iers.html) and [downloadable-data management](https://docs.astropy.org/en/stable/utils/data.html).

### Frames and units

- Synthetic propagator input/output: GCRS Cartesian position in metres and velocity in metres per second at the sample `obstime`.
- Earth-fixed state for maps and ground tracks: ITRS Cartesian position/velocity in metres and metres per second.
- Geodetic display: longitude, latitude, and ellipsoidal height derived from ITRS with WGS 84.
- TLE adapter, when added: SGP4 produces TEME kilometres and kilometres per second, then Astropy transforms TEME at the same `obstime` to ITRS. Do not reinterpret TEME as GCRS or rotate it with a hand-written Greenwich-angle shortcut.
- Orientation: body-to-ITRS unit quaternion with a documented component order and handedness. Position-derived orientation is only a visual fallback.

Astropy's satellite guide demonstrates the exact TEME-to-ITRS path and stresses attaching the observation time to the frame: [Working with Earth satellites](https://docs.astropy.org/en/stable/coordinates/satellites.html). Its coordinate graph also provides GCRS and ITRS transforms: [Astropy coordinates](https://docs.astropy.org/en/stable/coordinates/index.html).

### P0 force model

Pin the Earth constants in a named, versioned constant bundle instead of scattering literals. A suitable first bundle is:

```yaml
earth_model: p0-earth-v1
mu_m3_s2: 3.986004418e14
equatorial_radius_m: 6378137.0
j2: 1.08262668e-3
```

The central and J2 accelerations for GCRS Cartesian position `(x, y, z)` are:

```text
a_central = -mu * r_vec / |r|^3
k = 1.5 * J2 * mu * R^2 / |r|^5
a_J2 = k * [
  x * (5*z^2/|r|^2 - 1),
  y * (5*z^2/|r|^2 - 1),
  z * (5*z^2/|r|^2 - 3)
]
```

Integrate `dr/dt = v` and `dv/dt = a_central + a_J2` with RK4 at 1 second. In this short-horizon P0, the J2 symmetry axis is treated as fixed along the GCRS z-axis. That approximation must be stated; an operational propagator would use a fully specified Earth gravity frame and more forces.

WGS 84 publishes the semi-major axis and Earth gravitational constant used above; see the [NGA/Bowditch WGS 84 constants table](https://msi.nga.mil/api/publications/download?key=16693975%2FSFH00000%2FBowditch_Vol_1_LoRes.pdf&type=view). The J2 value and all constants must be provenance-tested against the chosen reference implementation before release.

NASA's [Earth Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html) independently lists the 6378.137 km equatorial radius, an approximate `J2 = 1082.63e-6`, and 1361 W/m² solar irradiance. It supports the scale of the P0 constants but does not replace the versioned constant bundle or numerical cross-validation.

## Sun, eclipse, attitude, and power

The Armenian note's “solar cycle” is interpreted here as the sunlight/eclipsed part of each orbit and its battery effect, not the Sun's approximately 11-year activity cycle.

### Sun vector

Use `astropy.coordinates.get_sun(time)` for the geocentric Sun vector in GCRS. Astropy states that its built-in ERFA method is within about 4 km in the Sun-Earth vector during 1900–2100, negligible for this first-order LEO power model: [Astropy `get_sun`](https://docs.astropy.org/en/stable/api/astropy.coordinates.get_sun.html).

### Eclipse fraction

Do not use only “satellite behind a spherical Earth” as a Boolean if solar generation is being plotted. Compute the apparent angular discs of Earth and Sun as seen from the spacecraft and their overlap:

- no overlap: `shadow_factor = 1`;
- Earth fully covers Sun: `shadow_factor = 0`;
- partial overlap: visible solar-disc area divided by total solar-disc area.

This produces a continuous `[0, 1]` penumbra factor. Use the same timestamp and GCRS vectors for the Sun, Earth, and spacecraft. Basilisk documents this conical/disc-overlap approach in its current [eclipse module](https://avslab.github.io/basilisk/Documentation/simulation/environment/eclipse/eclipse.html).

### Attitude truth

Solar incidence is undefined until attitude and panel articulation are defined. P0 should use a transparent prescribed law:

- bus attitude: nadir/LVLH pointing derived from GCRS position and velocity;
- panel articulation: ideal two-axis Sun tracking when sunlit;
- eclipse: retain the last valid panel attitude or use a deterministic park angle;
- output the bus quaternion and panel-normal vector as truth telemetry.

This is kinematic attitude truth, not an ADCS simulation. It gives a repeatable power baseline. A later `AttitudeProvider` can add body-fixed panels, one-axis tracking, slew rates, pointing errors, reaction wheels, and fault behavior without changing the power interface.

### Solar generation

For each panel:

```text
incidence = max(0, dot(panel_normal_gcrs, unit_sun_direction_gcrs))
distance_scale = (1 AU / sun_distance)^2
P_solar_W = solar_flux_1au_W_m2
            * distance_scale
            * area_m2
            * efficiency
            * incidence
            * shadow_factor
            * degradation_factor
```

`degradation_factor` is hidden scenario truth and must never be sent as normal telemetry. The visible symptoms are lower panel current/power at matched sunlight and incidence, followed by reduced charge rate and falling state of charge.

The structure matches Basilisk's documented first-order solar-panel equation. It deliberately omits self-shadowing, cell temperature coefficients, maximum-power-point tracking, harness losses, and detailed I-V curves.

### Loads and battery

Use mode-dependent loads and integrate stored energy, not an arbitrary SOC waveform:

```text
P_net = P_solar - sum(P_loads)

if P_net >= 0:
    delta_E_Wh = charge_efficiency * P_net * dt_s / 3600
else:
    delta_E_Wh = P_net / discharge_efficiency * dt_s / 3600

E_next = clamp(E + delta_E_Wh, 0, capacity_Wh)
SOC = E_next / capacity_Wh
```

Expose curtailed solar energy at full battery and unserved load at empty battery. A constant configured array/bus voltage may be used to derive current for the first demo, but it must be labeled a regulated-bus approximation, not a battery electrochemistry model. Basilisk's simple battery similarly integrates net power and clamps stored energy to capacity: [simple battery model](https://avslab.github.io/basilisk/Documentation/simulation/power/simpleBattery/simpleBattery.html).

## Concrete seed scenario

These values are a calibration starting point. They are selected to make the power chain observable in several orbits, not to describe a real spacecraft.

### Constellation

```yaml
epoch_utc: "2026-09-26T08:00:00Z"
telemetry_period_sim_s: 1
default_speed: 20

common_orbit:
  frame: GCRS
  semi_major_axis_m: 6928137       # about 550 km over WGS-84 equator
  eccentricity: 0.001
  inclination_deg: 97.6
  raan_deg: 0.0
  argument_of_perigee_deg: 0.0

satellites:
  - {id: SAT-001, true_anomaly_deg: 0.0}
  - {id: SAT-002, true_anomaly_deg: 120.0}
  - {id: SAT-003, true_anomaly_deg: 240.0}
```

This is a three-satellite train in one plane, which is enough to prove multi-object configuration and stagger eclipse entry. The two-body period from the configured semi-major axis is about 95.65 minutes. It should be described as “near-polar, sun-synchronous-like,” not certified sun-synchronous; exact Sun-synchronous design depends on the chosen gravity model and desired local solar time.

### Power

```yaml
solar_flux_1au_w_m2: 1361.0
panel_area_m2: 0.90
panel_efficiency: 0.28
panel_tracking: ideal_two_axis
battery_capacity_wh: 400.0
initial_soc: 0.85
operational_reserve_soc: 0.15
charge_efficiency: 0.95
discharge_efficiency: 0.95
loads_w:
  nominal: 150.0
  imaging_increment: 60.0
  downlink_increment: 40.0
```

Face-on solar power is about 343 W before shadow and degradation. Under an illustrative 35-minute eclipse in a 95.65-minute orbit, the simplified healthy energy balance is about +90 Wh/orbit, while a fully degraded factor of 0.35 is about -124 Wh/orbit at the nominal 150 W load. Actual eclipse duration comes from geometry.

### Hidden fault

```yaml
faults:
  - id: SAT-002-SOLAR-DERATING
    satellite_id: SAT-002
    parameter: power.solar_array.degradation_factor
    start_at_orbit: 1.5
    end_at_orbit: 3.5
    from: 1.0
    to: 0.35
    interpolation: linear
```

The intended story is: matched sunlight and incidence but progressively lower array power, shrinking charge margin, battery SOC trend reversal, forecasted reserve breach, and an operator recommendation to shed optional loads. The target is reserve crossing around orbit 5–6. That timing is a design hypothesis and must be calibrated by running the completed scenario; it is not a claimed result.

SAT-001 and SAT-003 are matched controls. They make it possible to distinguish a spacecraft-specific derating from a shared eclipse event.

## Cesium rendering contract

Use CesiumJS for the globe, camera, paths, labels, selection, and glTF models. The backend sends authoritative samples; the frontend keeps a short look-ahead buffer.

- Construct `SampledPositionProperty(ReferenceFrame.FIXED, 1)` from ITRS/ECEF position and velocity samples in metres and metres per second.
- Use Cesium's simulation `Clock` only to display/interpolate the backend timeline. On reconnect or seek, snap it to the server's simulation time.
- Do not compute longitude by rotating an inertial vector in JavaScript.
- Send an authoritative body-to-ECEF quaternion when attitude matters. `VelocityOrientationProperty` is acceptable only as an explicitly visual along-track fallback.
- Satellite model size may be exaggerated for selection. Orbit radius, ground track, timestamp, and position readout must remain physical.
- Render the Earth in its fixed map frame. An optional inertial camera can use Cesium's ICRF-to-fixed transform; it does not change the entity state.

Cesium's current API defines fixed-frame time-tagged position samples and optional derivatives in [`SampledPositionProperty`](https://cesium.com/learn/cesiumjs/ref-doc/SampledPositionProperty.html), a controllable simulated timeline in [`Clock`](https://cesium.com/learn/cesiumjs/ref-doc/Clock.html), and the inertial-to-Earth-fixed transform in [`Transforms.computeIcrfToFixedMatrix`](https://cesium.com/learn/cesiumjs/ref-doc/Transforms.html#computeIcrfToFixedMatrix). Cesium also states that an entity orientation is expressed with respect to ECEF: [`Entity.orientation`](https://cesium.com/learn/cesiumjs/ref-doc/Entity.html).

## Numerical and contract acceptance tests

These are release gates for the P0 physics layer.

### Clock and replay

- A 10,000-tick run emits exactly 10,000 monotonically increasing sample times separated by 1 simulated second.
- The same seed/configuration produces equal values after rounding contract fields to documented precision at 1x, 20x, and 100x.
- Pause/resume introduces no missing or duplicated simulation tick.
- No physics or event result depends on browser frame rate, WebSocket latency, or client count.

### Propagation

- Two-body-only circular case: measured period agrees with `2*pi*sqrt(a^3/mu)` within 0.1 s after interpolation of the crossing.
- Two-body-only case over 10 orbits: relative specific-energy drift and angular-momentum drift are each below `1e-8`.
- Central+J2 case over 24 hours: position differs by at most 100 m and velocity by at most 0.1 m/s from an independent high-tolerance integrator using the same force model and constants.
- Classical-elements-to-Cartesian and back round-trip meets `1e-9` relative tolerance away from singular circular/equatorial cases; singular input combinations are rejected or converted through a nonsingular representation.
- Every position stays above the configured Earth ellipsoid for this seed scenario; nonphysical initial states fail validation before the run.

### Time and frames

- GCRS -> ITRS -> GCRS round-trip at the same `obstime` is within 1 mm position and `1e-6 m/s` velocity.
- ITRS geodetic conversion matches Astropy/WGS 84 within 1 m altitude and `1e-8` radian latitude/longitude for fixed test vectors.
- A stored run declares Astropy, ERFA, and IERS-data versions and replays offline with no network request.
- Optional SGP4 adapter passes the official Vallado/CelesTrak reference vectors before accepting any TLE.

### Eclipse and power

- Clear Sun geometry returns `shadow_factor = 1`; central umbra returns `0`; all partial cases remain within `[0, 1]` and are continuous at contact boundaries.
- A face-on, uneclipsed panel matches the solar equation within 0.1%; a 60-degree incidence produces half power within 0.1%; a back-facing panel produces zero.
- In full eclipse, solar generation is exactly zero while loads continue.
- Constant-power charge and discharge cases match the analytic Wh change within 0.01 Wh over an hour and respect the 0/capacity clamps.
- Fault-disabled matched satellites with identical state/configuration have identical power values. Fault-enabled SAT-002 diverges only at the configured hidden parameter boundary.
- The seed scenario must be executed before demo freeze. Tune only declared scenario parameters until the reserve crossing occurs in the intended orbit window; save the run manifest and expected trace as a regression fixture.

### Visual

- At every exact backend sample time, Cesium's entity ECEF position matches the backend sample within floating-point conversion tolerance.
- Interpolated rendering never alters telemetry truth. The info panel always shows the latest authoritative sample timestamp, not the animation frame time.
- With a 1-second sample interval and velocity-assisted interpolation, maximum midpoint position error is measured against a denser backend truth trace and kept below 10 m for the seed orbit.
- Date/time, latitude, longitude, altitude, eclipse state, and SOC shown for a selected satellite all share the same sample timestamp.

## Honesty limits

The product can accurately claim: “a deterministic, time-tagged synthetic LEO operations simulation with central+J2 orbit dynamics, standard Earth-frame conversion, geometric Sun/eclipse coupling, prescribed attitude, first-order solar generation, mode loads, and battery energy balance.”

It cannot claim:

- precise knowledge or prediction of a real satellite orbit;
- full six-degree-of-freedom attitude dynamics or flight-software behavior;
- solar-cell, battery electrochemistry, thermal, RF, radiation, drag, or maneuver fidelity;
- operational readiness, collision avoidance, navigation-grade position, or hardware certification;
- that predictive performance on injected synthetic derating transfers to real spacecraft faults.

For the short P0 horizon, the main known orbit omissions are atmospheric drag, higher Earth harmonics, pole motion in the force model, Sun/Moon gravity, solar-radiation pressure, mass/area uncertainty, and maneuvers. The main power omissions are self-shadowing, temperature dependence, MPPT/regulator behavior, cell mismatch, battery voltage curves, rate capacity, and aging. Every run should expose `physics_model_id`, constants, assumptions, and hidden scenario truth to evaluators, while withholding hidden fault parameters from the health model.

## Assessment of the supplied visual reference

[OrbitSmith Solar System Explorer](https://orbitsmith.net/solar-system?lang=en) is a useful interaction reference for dark visual styling, camera navigation, object selection, date controls, and source/limits disclosure. It is not evidence for the proposed satellite physics. The page itself says that its planet positions are approximate, its explore mode compresses distances and enlarges bodies, and several bodies use simplified educational orbits. Its source uses approximate JPL Keplerian planet elements, not an Earth-satellite propagator. Reuse the interaction ideas and its explicit limitations panel; do not reuse its orbital code or visual scale as the simulator's truth layer.

Source-access note: the page returned valid HTML and was inspected directly, but the text-only web extractor returned an internal error. Its declared sources and limitations were available in the delivered HTML.

## Source hierarchy

Normative physics and API decisions above rely primarily on project/standards documentation and reference implementations:

- [CelesTrak: Revisiting SpaceTrack Report #3](https://celestrak.org/publications/AIAA/2006-6753/)
- [Astropy: Working with Earth satellites](https://docs.astropy.org/en/stable/coordinates/satellites.html)
- [Astropy: IERS data](https://docs.astropy.org/en/stable/utils/iers.html)
- [Astropy: Sun position](https://docs.astropy.org/en/stable/api/astropy.coordinates.get_sun.html)
- [Basilisk 2.11.1 documentation](https://avslab.github.io/basilisk/)
- [CesiumJS API](https://cesium.com/learn/cesiumjs/ref-doc/)
- [NGA WGS 84 constants](https://msi.nga.mil/api/publications/download?key=16693975%2FSFH00000%2FBowditch_Vol_1_LoRes.pdf&type=view)
- [NASA Earth Fact Sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html)

The supplied notes are treated as product hypotheses. In particular, “fault prediction” is a separate evaluation target from current anomaly detection: the simulator must emit hidden degradation trajectories and failure criteria so the health system can be scored on lead time, calibration, and false alerts rather than on a visually convincing dashboard.
