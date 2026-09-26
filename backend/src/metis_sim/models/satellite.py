"""Per-satellite composition of physical housekeeping and attitude models."""

from __future__ import annotations

import math
from typing import cast

from metis_sim.domain.physics import ChannelValue, Vector3
from metis_sim.domain.subsystems import HousekeepingConfiguration
from metis_sim.models.attitude import AttitudeModel
from metis_sim.models.electrical import electrical_sample
from metis_sim.models.payload import PayloadModel
from metis_sim.models.power import PowerAllocation
from metis_sim.models.thermal import ThermalModel


class Satellite:
    """Own independent spacecraft subsystem state behind one physical interface.

    Parameters
    ----------
    satellite_id : str
        Stable identity for this spacecraft instance.
    config : HousekeepingConfiguration
        Immutable parameters for its declared synthetic physical models.
    charge_efficiency, discharge_efficiency : float
        Efficiencies from the existing battery-energy ledger.

    Notes
    -----
    Only the run coordinator advances time. This composition receives actual
    interval powers and endpoint geometry, never scenarios, random traces,
    CSV files, wall clocks, database handles, or future outcomes.
    """

    def __init__(
        self,
        satellite_id: str,
        config: HousekeepingConfiguration,
        charge_efficiency: float,
        discharge_efficiency: float,
    ) -> None:
        self.satellite_id = satellite_id
        self._config = config
        self._charge_efficiency = charge_efficiency
        self._discharge_efficiency = discharge_efficiency
        self._thermal = ThermalModel(config.thermal)
        self._payload = PayloadModel(config.payload)
        self._attitude = AttitudeModel(config.attitude)
        self._fc_uptime_s = 0
        self._previous_quaternion: tuple[float, float, float, float] | None = None

    def step(
        self,
        *,
        dt_s: float,
        interval_mode: str,
        allocation: PowerAllocation,
        solar_flux_w_m2: float,
        position_gcrs_m: Vector3,
        velocity_gcrs_m_s: Vector3,
        acceleration_gcrs_m_s2: Vector3,
        sun_gcrs_m: Vector3,
        earth_pole_gcrs: Vector3,
    ) -> tuple[tuple[str, ChannelValue], ...]:
        """Emit one immutable one-hertz housekeeping measurement projection.

        Parameters
        ----------
        dt_s : float
            Zero for initial state or one second for an advancing interval.
        interval_mode : str
            Scheduled mode used by the completed interval's load allocation.
        allocation : PowerAllocation
            Existing conserved bus-power and battery-energy ledger.
        solar_flux_w_m2 : float
            Midpoint solar irradiance after distance and eclipse attenuation;
            initial sampling uses endpoint irradiance.
        position_gcrs_m, velocity_gcrs_m_s, acceleration_gcrs_m_s2 : tuple of float
            Authoritative endpoint inertial geometry and acceleration.
        sun_gcrs_m, earth_pole_gcrs : tuple of float
            Endpoint Sun position and the declared fixed GCRS Earth axis.

        Returns
        -------
        tuple of tuple
            Allowlisted immutable channel/value pairs. Circuit values and
            payload power/gate describe the interval; all other values are
            endpoint states. No internal heat ledger or private truth leaks.
        """
        if dt_s not in (0.0, 1.0):
            raise ValueError("Satellite dt_s must be zero or one second.")
        electrical = electrical_sample(
            self._config.electrical,
            allocation,
            self._charge_efficiency,
            self._discharge_efficiency,
        )
        supplied_fraction = (
            min(allocation.served_w / allocation.requested_w, 1.0)
            if allocation.requested_w > 0
            else 0.0
        )
        payload_w = (
            min(self._config.payload.active_power_w * supplied_fraction, allocation.served_w)
            if interval_mode == "payload_active"
            else 0.0
        )
        if payload_w > allocation.served_w:
            raise ValueError("Payload allocation exceeds the existing served-load budget.")
        payload = self._payload.step(dt_s, interval_mode, payload_w)
        temperatures = self._thermal.step(
            dt_s,
            solar_flux_w_m2,
            (electrical.battery_dissipation_w, allocation.served_w - payload_w, payload_w),
        ).temperature_k
        fully_powered = allocation.served_w > 0 and math.isclose(
            allocation.served_w, allocation.requested_w, rel_tol=1e-12, abs_tol=0
        )
        if dt_s:
            self._fc_uptime_s = self._fc_uptime_s + 1 if fully_powered else 0
        channels: list[tuple[str, ChannelValue]] = list(electrical.channels)
        channels.extend(
            (
                ("eps.battery_temperature_c", temperatures[0] - 273.15),
                ("fc.mcu_temperature_c", temperatures[1] - 273.15),
                ("fc.uptime_s", float(self._fc_uptime_s)),
                ("payload.electronics_temperature_c", temperatures[2] - 273.15),
                ("payload.power_w", payload.power_w),
                ("payload.uptime_s", float(payload.uptime_s)),
                ("payload.acquisition_active", float(payload.acquisition_active)),
                ("payload.image_count", float(payload.image_count)),
                ("payload.storage_used_bytes", float(payload.storage_used_bytes)),
                (
                    "payload.storage_fraction",
                    payload.storage_used_bytes / self._config.payload.storage_capacity_bytes,
                ),
            )
        )
        attitude = self._attitude.step(
            position_gcrs_m=position_gcrs_m,
            velocity_gcrs_m_s=velocity_gcrs_m_s,
            acceleration_gcrs_m_s2=acceleration_gcrs_m_s2,
            sun_gcrs_m=sun_gcrs_m,
            earth_pole_gcrs=earth_pole_gcrs,
        )
        quaternion = cast(tuple[float, float, float, float], attitude["adcs.attitude_quaternion"])
        previous = self._previous_quaternion
        if (
            previous is not None
            and sum(a * b for a, b in zip(previous, quaternion, strict=True)) < 0
        ):
            quaternion = cast(
                tuple[float, float, float, float], tuple(-value for value in quaternion)
            )
            attitude["adcs.attitude_quaternion"] = quaternion
            target = cast(tuple[float, float, float, float], attitude["adcs.target_quaternion"])
            attitude["adcs.target_quaternion"] = cast(
                tuple[float, float, float, float], tuple(-value for value in target)
            )
        self._previous_quaternion = quaternion
        channels.extend(attitude.items())
        return tuple(channels)
