"""Precomputed deterministic orbit-to-power simulation composition."""

from __future__ import annotations

from copy import deepcopy
from typing import cast

import numpy as np

from metis_sim.domain.config import SatelliteMode, SimulationConfig
from metis_sim.domain.physics import ChannelValue, OrbitSample, PhysicsSample, TruthSample, Vector3
from metis_sim.models.constants import (
    AU_M,
    EARTH_RADIUS_M,
    J2,
    MAX_ALTITUDE_M,
    MIN_ALTITUDE_M,
    MU_M3_S2,
)
from metis_sim.models.environment import illumination_fraction, solar_generation_w
from metis_sim.models.frames import FrameAdapter
from metis_sim.models.operations import operational_mode, resolve_operations
from metis_sim.models.orbit import (
    FloatArray,
    acceleration,
    elements_to_cartesian,
    hermite_midpoints,
    propagate,
)
from metis_sim.models.power import allocate_power
from metis_sim.models.satellite import Satellite
from metis_sim.models.scenarios import ReserveEvaluator, derating_multipliers


class RuntimeEnvelopeError(ValueError):
    """Signal an orbit leaving the supported 300–1500 km radial envelope.

    Notes
    -----
    The integrator never clamps coordinates to hide an unsupported orbit.
    """


class SimulationEngine:
    """Prepare a frozen configuration and expose immutable physical samples.

    Parameters
    ----------
    config : SimulationConfig
        Validated P0 configuration with immutable nested mappings.

    Notes
    -----
    ``initialize`` performs bounded CPU work and must run outside the HTTP
    event loop. ``sample`` and ``trajectory`` subsequently read cached arrays
    only. No database, HTTP, wall-clock pacing, or unseeded randomness enters
    the physical model. Precomputed future health is never part of preview.

    Examples
    --------
    Prepare a validated local configuration, then read the initial sample.
    Returned samples contain private truth and are for internal use only.

    >>> from pathlib import Path
    >>> from metis_sim.adapters.configuration import load_configuration
    >>> config = load_configuration(Path("configs/demo.yaml").read_text())
    >>> engine = SimulationEngine(config).initialize()
    >>> samples = engine.sample(0)
    >>> len(samples) == len(config.satellites)
    True
    """

    def __init__(self, config: SimulationConfig) -> None:
        self._config = config
        self._satellites = tuple(sorted(self.config.satellites, key=lambda item: item.satellite_id))
        self._indices = {item.satellite_id: index for index, item in enumerate(self._satellites)}
        self._initialized = False
        self._provenance: dict[str, object] = {}

    @property
    def config(self) -> SimulationConfig:
        """Return the immutable configuration bound to this engine.

        Returns
        -------
        SimulationConfig
            Validated configuration shared by preparation and sampling.
        """
        return self._config

    @property
    def duration_s(self) -> int:
        """Return the inclusive sampling limit from the bound configuration.

        Returns
        -------
        int
            Configured elapsed duration in SI seconds.
        """
        return self._config.run.duration_s

    @property
    def provenance(self) -> dict[str, object]:
        """Return a detached, JSON-compatible model provenance snapshot.

        Returns
        -------
        dict
            Recorded model inputs, including independent nested containers.
            Caller changes cannot alter the prepared engine's provenance.
        """
        return deepcopy(self._provenance)

    def initialize(self) -> SimulationEngine:
        """Validate time inputs and precompute geometry and the energy ledger.

        Returns
        -------
        SimulationEngine
            This prepared engine. Repeated calls are harmless and do not
            integrate a second time or change already calculated values.

        Raises
        ------
        EarthOrientationError
            Pinned Earth-orientation/leap-second inputs cannot cover the run.
        RuntimeEnvelopeError
            Propagated radius leaves the declared short-arc LEO envelope.
        """
        if self._initialized:
            return self
        self._frames = FrameAdapter(self.config.run.epoch_utc, self.duration_s)
        self._elapsed = np.arange(self.duration_s + 1, dtype=np.float64)
        self._timestamps = self._frames.datetimes(self._elapsed)
        axis = self._frames.pole_gcrs()
        initial = np.stack([elements_to_cartesian(item.orbit) for item in self._satellites])
        self._gcrs = propagate(initial, self.duration_s, axis)
        midpoints = hermite_midpoints(self._gcrs)
        for states in (self._gcrs, midpoints):
            altitude = np.linalg.norm(states[..., :3], axis=-1) - EARTH_RADIUS_M
            invalid = (
                (~np.isfinite(altitude)) | (altitude < MIN_ALTITUDE_M) | (altitude > MAX_ALTITUDE_M)
            )
            if np.any(invalid):
                tick, satellite_index = np.argwhere(invalid)[0]
                raise RuntimeEnvelopeError(
                    f"{self._satellites[satellite_index].satellite_id} leaves the supported "
                    f"radial altitude envelope near tick {tick}: {altitude[tick, satellite_index]:.3f} m."
                )
        self._itrs = self._frames.transform_states(self._gcrs, self._elapsed)
        self._geodetic = self._frames.geodetic(self._itrs[..., :3])
        half_times = np.arange(2 * self.duration_s + 1, dtype=np.float64) * 0.5
        sun_gcrs, sun_itrs = self._frames.sun_positions(half_times)
        self._sun_itrs = sun_itrs[::2]
        self._illumination = illumination_fraction(self._gcrs[..., :3], sun_gcrs[::2, None, :])
        midpoint_illumination = illumination_fraction(midpoints[..., :3], sun_gcrs[1::2, None, :])
        count, satellites = len(self._elapsed), len(self._satellites)
        self._incidence = np.empty((count, satellites), dtype=np.float64)
        # generation, requested, served, signed battery power, energy,
        # curtailed, unserved: all powers describe one completed interval.
        self._ledger = np.empty((count, satellites, 7), dtype=np.float64)
        self._modes: list[tuple[str, ...]] = []
        self._housekeeping: list[dict[str, FloatArray]] = []
        self._derating = np.ones((count, satellites), dtype=np.float64)
        self._interval_derating = np.ones((count, satellites), dtype=np.float64)
        self._truth_ticks = np.full((count, satellites, 3), -1, dtype=np.int64)
        self._scenarios = {item.satellite_id: item for item in self.config.scenario}
        for index, satellite in enumerate(self._satellites):
            profile = self.config.profiles[satellite.profile_id]
            panel, battery = profile.panel, profile.battery
            panel_parameters = {
                "area_m2": panel.area_m2,
                "efficiency": panel.efficiency,
                "conversion_efficiency": panel.conversion_efficiency,
                "irradiance_1au_w_m2": panel.irradiance_1au_w_m2,
            }
            endpoint_generation, self._incidence[:, index] = solar_generation_w(
                self._gcrs[:, index, :3],
                sun_gcrs[::2],
                self._illumination[:, index],
                **panel_parameters,
            )
            midpoint_generation, _ = solar_generation_w(
                midpoints[:, index, :3],
                sun_gcrs[1::2],
                midpoint_illumination[:, index],
                **panel_parameters,
            )
            operations = resolve_operations(
                satellite.operations, self.duration_s, satellite.orbit.a_m
            )
            modes = tuple(
                operational_mode(tick, satellite.initial_mode, operations) for tick in range(count)
            )
            self._modes.append(modes)
            scenario = self._scenarios.get(satellite.satellite_id)
            evaluator = None
            if scenario is not None:
                self._derating[:, index] = derating_multipliers(self._elapsed, scenario.points)
                self._interval_derating[0, index] = self._derating[0, index]
                self._interval_derating[1:, index] = derating_multipliers(
                    self._elapsed[1:] - 0.5, scenario.points
                )
                evaluator = ReserveEvaluator(scenario.outcome.reserve_soc, scenario.outcome.dwell_s)
            interval_generation = np.concatenate(([endpoint_generation[0]], midpoint_generation))
            interval_generation *= self._interval_derating[:, index]
            spacecraft = (
                Satellite(
                    satellite.satellite_id,
                    profile.housekeeping,
                    battery.charge_efficiency,
                    battery.discharge_efficiency,
                )
                if profile.housekeeping is not None
                else None
            )
            housekeeping: dict[str, FloatArray] = {}
            if spacecraft is not None:
                endpoint_distance = np.linalg.norm(
                    sun_gcrs[::2] - self._gcrs[:, index, :3], axis=-1
                )
                midpoint_distance = np.linalg.norm(
                    sun_gcrs[1::2] - midpoints[:, index, :3], axis=-1
                )
                interval_flux = panel.irradiance_1au_w_m2 * np.concatenate(
                    (
                        [(AU_M / endpoint_distance[0]) ** 2 * self._illumination[0, index]],
                        (AU_M / midpoint_distance) ** 2 * midpoint_illumination[:, index],
                    )
                )
                endpoint_acceleration = acceleration(self._gcrs[:, index, :3], axis)
            energy = battery.usable_capacity_wh * battery.initial_soc
            for tick in range(count):
                interval_mode = modes[max(tick - 1, 0)]
                allocation = allocate_power(
                    float(interval_generation[tick]),
                    profile.loads_w[cast(SatelliteMode, interval_mode)],
                    energy,
                    battery.usable_capacity_wh,
                    battery.charge_efficiency,
                    battery.discharge_efficiency,
                    battery.max_charge_w,
                    battery.max_discharge_w,
                    float(tick != 0),
                )
                energy = allocation.energy_wh
                self._ledger[tick, index] = (
                    allocation.generation_w,
                    allocation.requested_w,
                    allocation.served_w,
                    allocation.battery_power_w,
                    energy,
                    allocation.curtailed_w,
                    allocation.unserved_w,
                )
                if spacecraft is not None:
                    for name, value in spacecraft.step(
                        dt_s=float(tick != 0),
                        interval_mode=interval_mode,
                        allocation=allocation,
                        solar_flux_w_m2=float(interval_flux[tick]),
                        position_gcrs_m=self._vector(self._gcrs[tick, index, :3]),
                        velocity_gcrs_m_s=self._vector(self._gcrs[tick, index, 3:]),
                        acceleration_gcrs_m_s2=self._vector(endpoint_acceleration[tick]),
                        sun_gcrs_m=self._vector(sun_gcrs[2 * tick]),
                        earth_pole_gcrs=self._vector(axis),
                    ):
                        if value is None:
                            raise ValueError(
                                "A modeled housekeeping channel must have a physical value."
                            )
                        if name not in housekeeping:
                            shape = (len(value),) if isinstance(value, tuple) else ()
                            housekeeping[name] = np.empty((count, *shape), dtype=np.float64)
                        housekeeping[name][tick] = value
                if evaluator is not None:
                    evaluator.evaluate(tick, energy / battery.usable_capacity_wh)
                    self._truth_ticks[tick, index] = tuple(
                        value if value is not None else -1
                        for value in (
                            evaluator.first_entry_tick,
                            evaluator.active_entry_tick,
                            evaluator.failure_tick,
                        )
                    )
            for values in housekeeping.values():
                values.setflags(write=False)
            self._housekeeping.append(housekeeping)
        for array in (
            self._elapsed,
            self._itrs,
            self._geodetic,
            self._sun_itrs,
            self._illumination,
            self._incidence,
            self._ledger,
            self._derating,
            self._interval_derating,
            self._truth_ticks,
        ):
            array.setflags(write=False)
        self._provenance = {
            **self._frames.provenance,
            "earth_model": "wgs84_j2_v1",
            "orbit_model": "j2_cartesian",
            "integrator": "float64_rk4_fixed_1s",
            "midpoint_model": "cubic_hermite_from_rk4_endpoints",
            "sun_model": "astropy_builtin",
            "eclipse_model": "spherical_earth_finite_angular_disk_v1",
            "panel_model": "ideal_sun_tracking_equivalent_array",
            "mu_m3_s2": MU_M3_S2,
            "earth_equatorial_radius_m": EARTH_RADIUS_M,
            "j2": J2,
            "j2_fixed_axis_gcrs": axis.tolist(),
            "force_model_limits": "No drag, third bodies, maneuvers, tides, or radiation pressure; fixed J2 axis.",
            "eps_model_limits": "Ideal bus allocation and bounded energy store; no electrochemistry or ADCS dynamics.",
            "accuracy_claim": "Numerical agreement with the declared synthetic short-arc model; not flight ephemeris accuracy.",
        }
        if any(profile.housekeeping is not None for profile in self.config.profiles.values()):
            self._provenance.update(
                {
                    "housekeeping_model": "spacecraft_housekeeping_v1",
                    "electrical_model": "ideal_regulated_rails_v1",
                    "thermal_model": "three_node_euler_fixed_1s_v1",
                    "payload_model": "power_gated_camera_storage_v1",
                    "attitude_model": "ideal_lvlh_v1",
                    "magnetic_model": "centered_axial_dipole_v1",
                    "housekeeping_model_limits": (
                        "Declared synthetic parameters, not mission calibration. Ideal regulated rails; "
                        "three isothermal nodes with radiation and conduction, no Earth IR/albedo; "
                        "power-gated acquisition without downlink or heaters; ideal body tracking, "
                        "no actuator/control dynamics. Equivalent solar array remains independently "
                        "Sun tracking; curtailed generation is rejected upstream without onboard dump heat. "
                        "Unknown mission codes and unsupported sensors remain missing."
                    ),
                }
            )
        self._initialized = True
        return self

    def _validate_tick(self, tick: int) -> None:
        if not self._initialized:
            raise RuntimeError("Call initialize() before reading physical samples.")
        if type(tick) is not int or not 0 <= tick <= self.duration_s:
            raise ValueError(f"Tick must be an integer in [0,{self.duration_s}].")

    @staticmethod
    def _vector(values: FloatArray) -> Vector3:
        return float(values[0]), float(values[1]), float(values[2])

    def sample(self, tick: int) -> tuple[PhysicsSample, ...]:
        """Read one immutable physical endpoint for each configured satellite.

        Parameters
        ----------
        tick : int
            Elapsed tick in the inclusive configured interval.

        Returns
        -------
        tuple of PhysicsSample
            Stable satellite-ID ordering. Contains private truth for the
            repository boundary; public channels use an explicit allowlist.
        """
        self._validate_tick(tick)
        samples = []
        for index, satellite in enumerate(self._satellites):
            capacity = self.config.profiles[satellite.profile_id].battery.usable_capacity_wh
            generation, requested, served, battery_power, energy, curtailed, unserved = (
                float(value) for value in self._ledger[tick, index]
            )
            latitude, longitude, altitude = (float(value) for value in self._geodetic[tick, index])
            scenario = self._scenarios.get(satellite.satellite_id)
            first_entry, active_entry, failure = (
                int(value) if value >= 0 else None for value in self._truth_ticks[tick, index]
            )
            truth = TruthSample(
                fault_type=scenario.type if scenario else None,
                injection_start_tick=scenario.points[0].at_s if scenario else None,
                hidden_derating=float(self._derating[tick, index]),
                interval_derating=float(self._interval_derating[tick, index]),
                reserve_soc=scenario.outcome.reserve_soc if scenario else None,
                dwell_s=scenario.outcome.dwell_s if scenario else None,
                first_reserve_entry_tick=first_entry,
                active_reserve_entry_tick=active_entry,
                failure_tick=failure,
            )
            samples.append(
                PhysicsSample(
                    satellite_id=satellite.satellite_id,
                    tick=tick,
                    observed_at=self._timestamps[tick],
                    mode=self._modes[index][tick],
                    interval_mode=self._modes[index][max(tick - 1, 0)],
                    sample_window_s=int(tick != 0),
                    position_itrf_m=self._vector(self._itrs[tick, index, :3]),
                    velocity_itrf_m_s=self._vector(self._itrs[tick, index, 3:]),
                    latitude_deg=latitude,
                    longitude_deg=longitude,
                    altitude_m=altitude,
                    illumination_fraction=float(self._illumination[tick, index]),
                    panel_incidence_cosine=float(self._incidence[tick, index]),
                    solar_power_w=generation,
                    load_requested_w=requested,
                    load_served_w=served,
                    battery_power_w=battery_power,
                    battery_energy_wh=energy,
                    battery_soc=energy / capacity,
                    curtailed_power_w=curtailed,
                    unserved_power_w=unserved,
                    sun_position_itrf_m=self._vector(self._sun_itrs[tick]),
                    truth=truth,
                    housekeeping_channels=tuple(
                        (
                            name,
                            cast(
                                ChannelValue,
                                float(values[tick])
                                if values.ndim == 1
                                else tuple(float(value) for value in values[tick]),
                            ),
                        )
                        for name, values in self._housekeeping[index].items()
                    ),
                )
            )
        return tuple(samples)

    def trajectory(
        self, satellite_id: str, from_tick: int, to_tick: int, step: int = 10
    ) -> tuple[OrbitSample, ...]:
        """Read an orbit-only, time-tagged preview without future health data.

        Parameters
        ----------
        satellite_id : str
            Exact configured satellite identity.
        from_tick, to_tick : int
            Inclusive interval entirely within the configured run.
        step : int, optional
            Positive preview spacing in integer seconds. The final endpoint
            is included even if not divisible by the requested spacing.

        Returns
        -------
        tuple of OrbitSample
            Cached ITRS geometry shared with live telemetry, with no hidden
            scenario parameters or predicted power/energy measurements.
        """
        self._validate_tick(from_tick)
        self._validate_tick(to_tick)
        if from_tick > to_tick or type(step) is not int or step <= 0:
            raise ValueError("Preview requires an ordered interval and a positive integer step.")
        if satellite_id not in self._indices:
            raise KeyError(satellite_id)
        index = self._indices[satellite_id]
        ticks = list(range(from_tick, to_tick + 1, step))
        if ticks[-1] != to_tick:
            ticks.append(to_tick)
        result = []
        for tick in ticks:
            latitude, longitude, altitude = (float(value) for value in self._geodetic[tick, index])
            result.append(
                OrbitSample(
                    satellite_id=satellite_id,
                    tick=tick,
                    observed_at=self._timestamps[tick],
                    position_itrf_m=self._vector(self._itrs[tick, index, :3]),
                    velocity_itrf_m_s=self._vector(self._itrs[tick, index, 3:]),
                    latitude_deg=latitude,
                    longitude_deg=longitude,
                    altitude_m=altitude,
                    sun_position_itrf_m=self._vector(self._sun_itrs[tick]),
                )
            )
        return tuple(result)
