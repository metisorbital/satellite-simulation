"""Immutable domain values at the physics-to-application boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

Vector3 = tuple[float, float, float]
Rotation9 = tuple[float, float, float, float, float, float, float, float, float]
ChannelValue = float | Vector3 | tuple[float, float, float, float] | None


@dataclass(frozen=True, slots=True)
class TruthSample:
    """Private scenario evaluation at one physical endpoint.

    Attributes
    ----------
    hidden_derating : float
        Generation multiplier at the endpoint; never a public sensor.
    interval_derating : float
        Multiplier evaluated at the completed interval's midpoint.
    first_reserve_entry_tick : int or None
        First endpoint below the private reserve, even if it later recovered.
    active_reserve_entry_tick : int or None
        Start of the currently uninterrupted below-reserve period.
    failure_tick : int or None
        First state-driven confirmation tick; absent until dwell is satisfied.
    """

    fault_type: str | None = None
    injection_start_tick: int | None = None
    hidden_derating: float = 1.0
    interval_derating: float = 1.0
    reserve_soc: float | None = None
    dwell_s: int | None = None
    first_reserve_entry_tick: int | None = None
    active_reserve_entry_tick: int | None = None
    failure_tick: int | None = None


@dataclass(frozen=True, slots=True)
class SkippedOperation:
    """A scheduled window the onboard start guard refused.

    Attributes
    ----------
    label : str or None
        Public task identifier of the skipped window.
    mode : str
        Mode the window would have commanded.
    start_s, end_s : int
        The skipped half-open window.
    battery_soc : float
        State of charge at the start tick.
    min_start_soc : float
        Configured guard the state of charge was below.
    """

    label: str | None
    mode: str
    start_s: int
    end_s: int
    battery_soc: float
    min_start_soc: float


@dataclass(frozen=True, slots=True)
class OrbitSample:
    """Orbit-only preview with explicit terrestrial position and velocity.

    Attributes
    ----------
    observed_at : datetime
        UTC instant obtained by advancing elapsed SI seconds on TAI.
    position_itrf_m, velocity_itrf_m_s : tuple of float
        ITRS position and its rotating-frame time derivative.
    sun_position_itrf_m : tuple of float
        Geocentric Sun position in the same terrestrial frame.
    gcrs_to_itrs_rotation : tuple of float
        Row-major position rotation at ``observed_at``, containing nine elements.
    """

    satellite_id: str
    tick: int
    observed_at: datetime
    position_itrf_m: Vector3
    velocity_itrf_m_s: Vector3
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    sun_position_itrf_m: Vector3
    gcrs_to_itrs_rotation: Rotation9


@dataclass(frozen=True, slots=True)
class PhysicsSample:
    """Physical endpoint plus completed-interval power allocation.

    Notes
    -----
    Power fields are interval means over ``(tick-1, tick]`` except at tick
    zero, which has an instantaneous allocation and no energy advancement.
    This object contains private truth. Public transport must use the
    explicit ``public_channels`` projection and selected envelope fields.
    ``skipped_operation`` is set only at the start tick of a window the
    onboard start guard refused.
    """

    satellite_id: str
    tick: int
    observed_at: datetime
    mode: str
    interval_mode: str
    sample_window_s: int
    position_itrf_m: Vector3
    velocity_itrf_m_s: Vector3
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    illumination_fraction: float
    panel_incidence_cosine: float
    solar_power_w: float
    load_requested_w: float
    load_served_w: float
    battery_power_w: float
    battery_energy_wh: float
    battery_soc: float
    curtailed_power_w: float
    unserved_power_w: float
    sun_position_itrf_m: Vector3
    truth: TruthSample
    housekeeping_channels: tuple[tuple[str, ChannelValue], ...] = ()
    skipped_operation: SkippedOperation | None = None

    def public_channels(self) -> dict[str, float | list[float] | None]:
        """Project only the immutable public catalog's physical values.

        Returns
        -------
        dict
            Exact channel IDs and finite primitive values, with no scenario,
            reserve threshold, future state, or private configuration.
        """
        channels: dict[str, float | list[float] | None] = {
            "orbit.position_itrf_m": list(self.position_itrf_m),
            "orbit.velocity_itrf_m_s": list(self.velocity_itrf_m_s),
            "orbit.latitude_deg": self.latitude_deg,
            "orbit.longitude_deg": self.longitude_deg,
            "orbit.altitude_m": self.altitude_m,
            "environment.illumination_fraction": self.illumination_fraction,
            "environment.panel_incidence_cosine": self.panel_incidence_cosine,
            "eps.solar_power_w": self.solar_power_w,
            "eps.load_requested_w": self.load_requested_w,
            "eps.load_served_w": self.load_served_w,
            "eps.battery_power_w": self.battery_power_w,
            "eps.battery_energy_wh": self.battery_energy_wh,
            "eps.battery_soc": self.battery_soc,
            "eps.curtailed_power_w": self.curtailed_power_w,
            "eps.unserved_power_w": self.unserved_power_w,
        }
        channels.update(
            (name, list(value) if isinstance(value, tuple) else value)
            for name, value in self.housekeeping_channels
        )
        return channels
