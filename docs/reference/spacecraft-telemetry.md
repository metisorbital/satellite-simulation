---
title: Spacecraft Telemetry Models and Export
description: Configure the optional physical telemetry models, interpret their channels and limits, and export committed measurements for ML experiments.
content-type: reference
audience: developers and ML engineers
last-verified: 2026-09-26
---

# Spacecraft Telemetry Models and Export

`spacecraft.v1` extends the 15-channel `power-leo.v1` catalog with declared electrical, thermal, payload, attitude, and magnetic-field models.
It contains **41 modeled channels and 12 explicitly unavailable channels**, counting a vector as one channel.
The [210-field sample inventory](sample-telemetry.md) defines the kinds of telemetry of interest; it is not a claim that 210 independent sensors are modeled.
CSV values are never loaded, replayed, interpolated, or fitted by these models.

The simulator remains a synthetic measurement source with a database and public read APIs.
The Flutter viewer includes a catalog-backed telemetry dashboard; open **Telemetry dashboard** after selecting a satellite and starting a run.
Its Overview, EPS, Flight computer, Payload, ADCS, and Space weather tabs show committed samples with units, UTC time, quality, and explicitly unavailable channels.
The 1/5/10-minute controls filter recent received history (up to 600 samples per satellite; initial/reconnect snapshots contain up to 41), rather than fetching a complete historical window.
Model training, health inference, and real-spacecraft calibration remain separate work.
See the [data contracts](../contracts.md) and [physics model](../physics-model.md) for the unchanged clock, orbit, energy, and privacy boundaries.
Executed checks and remaining gates are recorded in [telemetry validation](../validation/spacecraft-telemetry.md).

## Select the Extension

Use [the telemetry demonstration configuration](../../configs/telemetry-demo.yaml).
A profile opts in with `sensors.catalog: spacecraft.v1` and a `housekeeping` object; `power-leo.v1` profiles exclude `housekeeping`.
Its immutable configuration selects `electrical`, `thermal`, `payload`, and `attitude` parameters, with typed defaults for omitted members.
Payload active power must fit within the existing `loads_w.payload_active` total; it is not an additional load.

The example uses an 8.2 V battery terminal, 12 V solar branch, 5 V load bus, and a 20 W payload requiring five fully powered seconds per image.
Each image occupies 1,048,576 bytes in a 1,073,741,824-byte store.
These are illustrative configuration choices, not parameters inferred from a real spacecraft.
The example schedules a 300-second `METIS-02` payload operation beginning at simulated second 3,600 and repeats it once per nominal orbit; its solar derating begins later, at second 5,400.
The fixed two-body cadence and partial final-window behavior are defined in [schedule payload operations](../physics-model.md#schedule-payload-operations).

Sampling remains one second in simulated UTC: an initial state at sequence zero, then each completed tick through the configured duration.
At zero, `sample_window_s=0` and no energy, temperature, uptime, or image count advances; later windows are one second.
Wall-clock speed and pause controls do not change the numerical step.

## Interpret the Physical Models

### Regulated Electrical Rails

The existing conserved EPS allocation owns generation `G`, served load `S`, charging power `C`, and discharging power `D`, all in watts.
For configured rail voltages and existing battery efficiencies:

```text
I_battery_in  = eta_charge * C / V_battery
I_battery_out = D / (eta_discharge * V_battery)
I_solar      = G / V_solar
I_bus        = S / V_bus
Q_converter  = C * (1 - eta_charge) + D * (1 / eta_discharge - 1)
delta_E_Wh   = V_battery * (I_battery_in - I_battery_out) * dt_s / 3600
```

IN and OUT are separate nonnegative currents at the ideal energy-store terminal; `eps.battery_power_w` retains its bus-side positive-discharge convention.
Rail voltage/current outputs describe the interval power allocation, including the interval that empties a battery.
An inactive solar/load branch reports zero voltage; the battery voltage is zero only when the store is empty and neither charging nor discharging.
The regulated value is an equivalent circuit assumption, not resolved switching behavior within a depleted interval.
There is no cell electrochemistry, voltage sag, resistance/ripple model, MPPT transient, or temperature feedback into efficiency, capacity, or voltage.

### Three Thermal Nodes

The battery, avionics bus, and payload are each one isothermal node with capacity `H_i` in J/K.
The model uses a one-second forward-Euler update, with temperatures in kelvin:

```text
F = solar_irradiance_1au * (AU / sun_distance)^2 * illumination_fraction
Q_solar_i = absorptivity_i * effective_solar_area_i * F
Q_radiated_i = emissivity_i * radiating_area_i * sigma * (T_i^4 - T_sink^4)
T_i_next = T_i + dt_s / H_i * (
    Q_electrical_i + Q_solar_i - Q_radiated_i + sum(K_ij * (T_j - T_i))
)
```

`sigma=5.670374419e-8 W/(m² K⁴)`; symmetric battery–bus and payload–bus conduction cancels in the network heat sum.
Electrical heat is `(Q_converter, S - P_payload, P_payload)`, assigning served electrical work to these nodes once.
The incident flux uses midpoint distance/eclipse geometry after the initial sample; solar electrical derating does not alter that incident environmental flux.
Temperature telemetry converts endpoint kelvin to °C.
The effective absorbing areas are prescribed model parameters, not resolved surface normals.
Curtailed generation is rejected upstream without onboard dump heat.
Earth IR, albedo, thermostats, heaters, individual component hot spots, and thermal degradation are absent; leaving the supported 100–500 K envelope raises an error instead of clamping temperature.

### Powered Camera and Storage

In a `payload_active` interval, `P_payload = min(P_active * S/L, S)`, where `L` is total requested load; otherwise payload power is zero.
The model allocates zero when `L=0` and keeps payload power within the already-served bus total.
Acquisition requires the scheduled payload mode, its full configured power, and room for a complete image.
Each consecutive powered exposure second advances progress; after `image_period_s`, one image and its bytes are added.
Interruption resets incomplete exposure progress. Capacity stops acquisition without deleting data or implicitly shutting off the scheduled payload load.

`payload.uptime_s` counts consecutive fully powered active intervals and resets on power shortage or leaving payload mode.
`fc.uptime_s` counts consecutive intervals in which the complete requested load is supplied and resets on a deficit.
`payload.acquisition_active` is the modeled interval gate, not a mission camera-status code; counters and storage are endpoint values.
There is no download, compression, file deletion, dual-camera implementation, or mission-specific status encoding.

### Ideal Attitude and Magnetic Field

The body follows an ideal LVLH prescription from authoritative GCRS orbit state: `z=-r/|r|`, `y=-(r×v)/|r×v|`, `x=y×z`.
The matrix with those body axes as columns maps body vectors into GCRS.
Quaternions use Hamilton **`[w,x,y,z]`**, scalar first, for that active body-to-GCRS rotation.
The stateless kernel selects a canonical equivalent sign; the satellite composer flips it when needed to keep successive quaternion dot products nonnegative.
Target equals actual attitude by prescription, so off-nadir and control-error values are zero assumptions, not demonstrated control performance.

Body angular rate is `R.T * 0.5 * sum(e_i × derivative(e_i))`, with axis derivatives using the same position, velocity, and J2 acceleration as the orbit model.
The body Sun vector is the unit geometric spacecraft-to-Sun direction, even during eclipse; it is not a detected optical-sensor signal.
The centered axial magnetic approximation uses `m_hat=-earth_pole_GCRS` and:

```text
B_GCRS = B_equator * (R_E / |r|)^3 * (3 * dot(m_hat, r_hat) * r_hat - m_hat)
B_body = R.T * B_GCRS
```

The Earth pole is fixed at the run epoch; the configured default equatorial strength is 30.6 µT.
Dipole tilt, higher multipoles, secular variation, and space weather are excluded.
No gyro bias/noise, optical tracker, feedback controller, torque, or reaction-wheel dynamics is solved.
The equivalent solar array remains independently Sun tracking, as if freely gimbaled relative to the LVLH body; neither gimbal mechanics nor body-fixed panel incidence is modeled.

## Relate Sample Families to Available Channels

These are scope correspondences, not a calibrated adapter from mission fields to simulator fields.
Canonical channel definitions, units, shapes, and availability come from `GET /v1/catalog?version=spacecraft.v1`.

| Sample family | Canonical coverage and limits |
|---|---|
| Battery voltage, IN/OUT current | `eps.battery_voltage_v`, `eps.battery_current_in_a`, `eps.battery_current_out_a`; no reconstructed source-hour voltage mean/min/max |
| Solar/converter/output currents and voltages | `eps.solar_voltage_v`, `eps.solar_current_a`, `eps.bus_voltage_v`, `eps.bus_current_a`; equivalent branches, not each panel, converter, or numbered output |
| EPS, FC, and payload temperatures | `eps.battery_temperature_c`, `fc.mcu_temperature_c`, `payload.electronics_temperature_c`; three nodes, not every named source sensor |
| Uptime, acquisition, power, memory | `fc.uptime_s`, `payload.uptime_s`, `payload.power_w`, `payload.acquisition_active`, `payload.image_count`, `payload.storage_used_bytes`, `payload.storage_fraction`; no source camera codes, downloads, or heater PWM |
| Navigation and ECI position | Existing `orbit.*_itrf_*`/geodetic channels plus `orbit.position_gcrs_m`, `orbit.velocity_gcrs_m_s`; no GPS measurement errors or separate mission ground-speed scalar |
| Attitude/target quaternions, rates, Sun/magnetic vectors, pointing error | `adcs.attitude_quaternion`, `adcs.target_quaternion`, `adcs.angular_velocity_rad_s`, `adcs.sun_vector_body`, `adcs.magnetic_field_body_t`, `adcs.off_nadir_angle_deg`, `adcs.control_error_deg`; ideal prescribed values with the conventions above |
| Watchdog and GNSS | Missing: `eps.watchdog_remaining_s`, `fc.gnss_satellites_in_view`, `fc.gnss_satellites_tracked`, `fc.gnss_fix_quality` |
| Wheel/actuator and mission ADCS codes | Missing: `adcs.reaction_wheel_speed_rpm`, `adcs.reaction_wheel_pressure_pa`, `adcs.demanded_torque_nm`, `adcs.controller_mode`, `adcs.star_tracker_quality` |
| External space weather | Missing: `space_weather.kp_index`, `space_weather.proton_flux`, `space_weather.x_ray_flux` |

The 12 unavailable catalog entries are emitted as `{value: null, quality: "missing"}`; absence of a physical model is not a zero reading.
Other source-only details without a canonical channel remain unimplemented, rather than becoming additional invented measurements.

## Read Reports and Export Measurements

After [local setup](../getting-started.md), apply the schema migration and start a paused demonstration with ten committed seconds:

```bash
uv run metis-sim migrate
uv run metis-sim demo --config configs/telemetry-demo.yaml --at 10
```

Use the existing controls to resume; `--at 3900` instead prepares the example's completed payload window.
In a second terminal at the repository root, load local credentials without printing them and identify this loopback demo run:

```bash
set -a
. .local/runtime.env
set +a
telemetry_base=http://127.0.0.1:8000
telemetry_run_id=$(curl -fsS "$telemetry_base/v1/viewer/bootstrap" | uv run python -c \
  'import json, sys; print(json.load(sys.stdin)["run"]["run_id"])')
curl -fsS "$telemetry_base/v1/catalog?version=spacecraft.v1" \
  -H "Authorization: Bearer $METIS_CONSUMER_TOKEN"
curl -fsS "$telemetry_base/v1/runs/$telemetry_run_id/telemetry-report" \
  -H "Authorization: Bearer $METIS_CONSUMER_TOKEN"
uv run python examples/export_run.py --url "$telemetry_base" --run "$telemetry_run_id" \
  --output ".local/datasets/$telemetry_run_id"
```

The report accepts inclusive `from_sequence` and `through_sequence`; its default end captures the current committed tick.
It reads persisted public frames only, rejects future windows, reports gaps with `complete_window=false`, and returns `410` for expired runs.
An unstarted run has an empty window ending at `-1`.
Coverage describes the requested window, not whether the configured run finished.
Quality counts remain separate; only valid values enter scalar/elementwise min/max/mean, including a valid sequence-zero sample.
Interval integrals and weighted means exclude zero-duration samples and invalid/missing/saturated readings; integrals have channel-unit seconds, with `valid_interval_duration_s` stating coverage.
Endpoint channels are not integrated. Quaternion component statistics are not an attitude average.

The existing [durable stream API](../api.md) still provides original frames and cursors.
The standalone exporter captures a report boundary, downloads each stream through that sequence, checks identities/catalogs/gaps, and publishes a new directory only after the complete export succeeds.
Later committed frames cannot extend the captured dataset; existing destination directories are rejected.

| Output | Contents |
|---|---|
| `telemetry.jsonl` | Original public frames, ordered by satellite and sequence, without resampling or filling missing values |
| `report.json` | Captured bounds, per-stream coverage, quality counts, statistics, and public model provenance |
| `catalogs.json` | Each included stream's versioned channel metadata |
| `dataset.json` | Run identity, frame count, boundary, telemetry SHA-256, filenames, and grouping guidance |

## Keep ML Evaluation Separate

The initial health mechanism remains private solar-array derating: generation changes the conserved energy/current ledger, converter/load heat, and eventual power availability for scheduled acquisition.
Thermal state does not feed back into battery health, and no additional hardware fault mechanism or trained inference model is implied.
The example's later deficit and earlier payload schedule must not be presented as an executed acquisition-failure experiment.

Public exports retain run/stream/satellite identities, UTC sample times, values, and quality, while excluding seeds, scenario schedules, hidden thresholds, and outcome labels.
Authorized evaluators obtain truth separately through `GET /v1/evaluation/runs/{run_id}/truth`; the private reproducibility manifest remains under `GET /v1/operator/runs/{run_id}/manifest`.
Keep complete runs together in train/validation/test splits, and use authorized private manifests to group regenerated or matched executions that share underlying conditions.
Random row splits can leak adjacent trajectory information. Preserve censored outcomes rather than labeling every run without an observed failure permanently healthy.
The saved configuration, model/source/dependency provenance, and seed support regeneration in the pinned environment; new run/stream IDs and wall times differ.
Synthetic experiments establish behavior under these equations, not prediction accuracy on operating spacecraft.
