# Define the Satellite Telemetry Simulator Scope

## Make the Product Claim Precisely

The product to build is a deterministic, configurable Python service that simulates a small LEO constellation's operations and emits physically constrained synthetic telemetry.
It is a source of testable telemetry and a visual operations demo.
It is not a flight-qualified digital twin, a general astrodynamics package, a hardware simulator, or an AI health product.

The simulator's causal chain is:

```text
configuration + seed + simulated time
  -> orbit and Sun/Earth/ground-station geometry
  -> eclipse, solar availability, and scheduled operational mode
  -> load and energy-balance state
  -> observable telemetry
  -> optional latent fault influence
```

Every displayed satellite position, sun/eclipse state, power reading, and ground-pass indicator must come from the same simulated timestamp and state.
The front end must not independently approximate an orbit or fabricate a power series.

The future analytics product may consume the public telemetry contract, but detection, forecasting, alerting, recommendation, model training, model scores, and notification delivery are outside this repository's simulator scope.

## Set the P0 Boundary

P0 should provide a configuration schema that can express several satellites, then demonstrate two or three LEO satellites using one deterministic propagation and telemetry path per satellite.
Do not build a separate single-satellite code path.
Supporting an arbitrary fleet size, crosslink simulation, formation flying, collision avoidance, or fleet optimization is not a P0 requirement.

P0 needs these modules and public contracts:

| Module | Required responsibility | P0 acceptance outcome |
| --- | --- | --- |
| Simulation clock | Advance only simulated UTC time; support start, pause, reset, speed, seek/replay, and a seed. | Resetting the same configuration, seed, and start time reproduces the same state and telemetry sequence. |
| Constellation configuration | Validate satellite IDs, epoch, circular-orbit elements, power parameters, initial battery state, operating schedule, ground stations, and scenario references. | An invalid capacity, duplicate ID, nonsensical orbit, or unknown scenario fails before a run begins. |
| Orbit and frames | Propagate a deliberately limited circular two-body LEO orbit and derive ECI/ECEF position, geodetic latitude/longitude/altitude, and velocity. | The satellite has a continuous ground track, stays near its configured altitude, and completes a plausible LEO period. |
| Environment | Compute one Sun vector and eclipse state from Earth occlusion; calculate elevation to configured ground stations. | Solar generation is exactly zero in eclipse; pass start/end events agree with the displayed elevation threshold. |
| Operations/load model | Schedule `idle`, `imaging`, `downlink`, and `safe` modes, while keeping eclipse as an environmental condition rather than a competing mode. | Imaging and downlink increase demand according to their configured loads; safe mode lowers the nonessential load. |
| EPS model | Advance battery energy/SOC from solar generation less load, with bounded SOC, voltage response, and a simple charge/discharge efficiency. | The energy balance closes per step within a declared numerical tolerance, and no signal violates its bounds. |
| Scenario engine | Apply a deterministic, time-indexed latent parameter profile and produce a private truth trace. | An operator telemetry stream contains no scenario/fault ID or latent parameter, while a test-only trace contains onset, severity, and threshold-crossing labels. |
| Telemetry/event publisher | Emit versioned snapshots/events with simulated timestamps and satellite IDs. | Every message can be joined to its state and is monotonic by simulation time per satellite. |
| Visualization adapter | Supply positions, trail samples, state, selection telemetry, and ground-pass/eclipse events for an interactive Earth view. | Selecting a marker shows telemetry for that exact satellite and timestamp; pausing freezes both the map and values. |

P0 telemetry should stay near 15–20 signals: position/velocity; eclipse and station-pass booleans; mode; solar-array current/power; load power; battery SOC, current, voltage, and energy; bus voltage; and a few explicitly derived health-neutral status fields.
It is sufficient for an operations story because orbit, illumination, payload scheduling, and power affect one another visibly.

P0 progressive scenarios should be limited to power-system effects:

- `battery_capacity_and_resistance_degradation`: latent usable capacity decreases and internal resistance increases; under the same eclipse/load conditions this produces earlier SOC depletion and voltage sag.
- `solar_array_efficiency_loss`: latent available solar output decreases only when illuminated; the downstream effect is lower charge energy and later SOC decline.

Both scenarios must state that their accelerated timelines are synthetic demo parameters, not spacecraft life estimates.
They should share the same mechanism as nominal EPS and differ only through private parameters.
That is more credible than directly overwriting a visible telemetry channel.

## Defer P1 Deliberately

P1 can add one subsystem at a time behind the same environment, clock, state, telemetry, and truth contracts:

| Candidate | Why it is deferred | Guardrail for adding it |
| --- | --- | --- |
| First-order thermal model | A plausible temperature depends on absorptivity, dissipation, view factors, and mode-dependent heat sources. | Add only when an engineer can specify inputs, bounds, time constants, and a validation trace. |
| Reaction-wheel/ADCS degradation | It needs an attitude/torque/load model before wheel current, RPM, temperature, and pointing error can be causally linked. | Do not emit wheel telemetry merely as correlated noise. |
| Communications | Link quality depends on geometry, antenna, radio state, and chosen abstractions. | Start with ground-station visibility, then specify an explicit simplified link model before SNR, packet loss, or rate are shown. |
| OBC/payload | CPU, memory, storage, camera temperature, and image products need an operational workload model. | Model the workload first; do not add a memory leak solely to create a reset demo. |
| Satellite assets | A graphical model is presentation material, not simulation state. | Preserve optional `asset_url` and attitude fields in the view contract; use a default marker until assets exist. |

P1 scenarios may include thermal-control degradation, reaction-wheel friction, and a memory leak only after their respective causal model exists.
An immediate communications interruption is a separate incident scenario, not predictive maintenance.

## Keep These Items Out of Scope

- Full 6-DOF attitude dynamics, reaction-wheel dynamics, flexible bodies, detailed magnetorquers, finite-element thermal analysis, RF link budgets, radiation, CCSDS, flight software, and hardware-in-the-loop.
- Live TLE ingestion, operational commands, real mission telemetry, collision manoeuvres, and any claim of flight readiness.
- AI inference endpoints, anomaly scores, health scores, remaining-useful-life estimates, alert routing, and operator recommendations.
- A claim that synthetic fault onset proves future-failure prediction or mission-life extension.

## Preserve the Evidence Boundary

The simulator must generate two logically separate outputs.

| Output | Audience | Contains |
| --- | --- | --- |
| Public telemetry/events | UI and future analytics consumer | Observable state, measurements, modes, geometry, and data-quality metadata only. |
| Private truth/evaluation trace | Scenario tests and offline evaluation | Scenario ID, latent parameter history, injected-fault onset, severity, failure threshold, and run seed. |

The private trace is required to evaluate a downstream model against known synthetic events.
It must never be merged into the public telemetry payload, UI selection data, or downstream model features.
This separation prevents label leakage.

The simulator can validate its own product behavior without implementing ML:

1. Run each nominal configuration for at least several orbits and check invariants: `0 <= SOC <= 1`, solar power is zero in eclipse, stored-energy change matches net energy, and timestamps are monotonic.
1. Run the same scenario with the same seed twice and compare emitted public and private traces.
1. Run nominal and faulted scenarios under the same schedule/seed, then verify the expected observable divergence begins after the private onset and obeys the causal direction.
1. Verify the public trace has no prohibited truth fields and does not expose a scenario name through a synthetic status flag.
1. Verify the UI uses the selected satellite's public snapshot and shared simulation timestamp.

This yields meaningful synthetic validation of the simulator itself.
It does not measure detection precision, forecast lead time, or remaining-useful-life accuracy; those are future analytics evaluations that must define their own held-out data and metrics.

## Use Research Sources Correctly

### XJTU-SPS

[XJTU-SPS](https://diyi1999.github.io/XJTU-SPS/) is the closest relevant source for the P0 EPS model.
Its physical hardware fault-injection platform covers solar array, batteries, charge/discharge regulators, shunt regulation, distribution, and loads.
It describes a 95-minute LEO-like cycle with 60 minutes of sunlight and 35 minutes of shadow, plus mode-dependent power conditions such as charge, shunt, joint supply, idle, and discharge.
This directly supports modeling the causal relation among illumination, mode-dependent load, solar output, battery state, and bus behavior.

Use it to sanity-check mode transitions, signal ranges after inspecting the files, and the shape of EPS relationships.
Do not describe it as real orbital telemetry or use it to validate the other planned subsystems.
The authors explicitly say that its fault data is produced by physical hardware fault injection rather than its mathematical-physical simulation model.
Its forecasting/reconstruction subset contains no anomalies/faults, while its fault-localization/diagnosis subset has 17 EPS fault classes.
It therefore supports a power-system reference and offline analytics experimentation, not a general satellite health dataset or a ground-truth source for this simulator.

### ESA-ADB / ESA Anomaly Dataset

The [ESA-ADB project](https://ai4gs.space-codev.org/esa-adb/) and [ESA Anomaly Dataset record](https://zenodo.org/records/15237121) are relevant future benchmark sources for anomaly detection.
ESA describes the dataset as curated anomaly annotations from three real ESA missions, but the v2 record distributes three archives totaling 11.6 GB and its stated purpose is anomaly benchmarking.
It is not a quick hackathon dependency, a telemetry source for a fictional constellation, or evidence that a future-failure model has been validated.
Any adoption must inspect license, schema, channel metadata, split strategy, and temporal leakage before it is used.

### Telemanom

[Telemanom](https://github.com/khundman/telemanom) and its [original paper](https://arxiv.org/abs/1802.04431) are relevant only as an anomaly-detection baseline and evaluation reference.
The published repository says it trains LSTMs on normal behavior and detects anomalous prediction errors; its released SMAP/MSL data is anonymized, pre-scaled, and has anonymized command information.
It supplies anomaly intervals, not causal component-degradation truth or remaining-useful-life labels.
It must not be cited to justify failure prediction, physical telemetry calibration, or a claim about satellite lifetime.

### Basilisk and SGP4

[Basilisk](https://avslab.github.io/basilisk/) is a mature spacecraft simulation framework with modular Python access to C/C++ models, including 6-DOF and effectors, validation tests, and a separate 3D visualizer.
It is appropriate as a future high-fidelity comparison/integration option.
For this P0 it would add integration and model-configuration cost without improving the required orbit-to-power causal story.
Keep an adapter boundary around the orbit/state provider so it can be replaced later.

[SGP4](https://celestrak.org/publications/AIAA/2006-6753/) is a TLE/GP propagation method, not a generic guarantee of physical fidelity.
Use it only if the demo needs a real TLE ground track and disclose the selected element epoch/source.
A configured, deterministic circular two-body LEO propagator is preferable for a fictional satellite because the configuration truth remains controlled and reproducible.

## Treat the Market Landscape as Positioning, Not Evidence

The supplied [satellite-operations landscape](https://satellite-operations-landscape.hakobtam.chatgpt.site/?sort=match) is a useful orientation map, not a requirements source or independent product validation.
The page itself describes its rankings as editorial, its non-government figures as company-reported and unaudited, and explicitly says anomaly detection alone does not prove extra years of life.

Its useful conclusion is that monitoring, diagnosis, reliability forecasting, collision avoidance, servicing, network optimization, and mission scheduling are different products with different evidence requirements.
The current simulator should not collapse them into an unsubstantiated promise to extend satellite lifetime.
The landscape's individual source links are mainly vendor pages, which establish that a company makes a product claim but do not independently establish performance, fleet adoption, revenue, prediction accuracy, or years of added life.

The simulator's differentiated, defensible demonstration is narrower: an operator can inspect a physically constrained constellation state, understand why power telemetry changes, replay a reproducible progressive scenario, and give a future analytics service an evaluation-safe telemetry/ground-truth boundary.
