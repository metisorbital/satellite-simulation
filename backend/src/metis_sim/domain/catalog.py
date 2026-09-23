"""Allowlisted public measurement catalog for the P0 power LEO producer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ChannelDefinition:
    """Describe a public telemetry channel without simulator internals.

    Parameters
    ----------
    channel_id : str
        Stable channel identifier.
    unit : str
        Display and interpretation unit.
    value_type : str
        Scalar or fixed vector shape.
    origin : str
        Whether the value is measured by a sensor or derived.
    sampling_semantics : str
        Whether the value describes an endpoint or interval mean.
    resolution : float | None
        Declared sensor resolution; ``None`` means a derived value.
    coordinate_frame : str | None
        Coordinate frame for vector channels, when applicable.
    cadence_s : int
        Nominal sample cadence in simulated seconds.
    description : str
        Public explanation of the channel's meaning and limits.
    """

    channel_id: str
    unit: str
    value_type: Literal["scalar", "vector[3]"]
    origin: Literal["sensor", "derived"]
    sampling_semantics: Literal["endpoint", "interval_mean"]
    resolution: float | None
    coordinate_frame: str | None
    cadence_s: int
    description: str


def _channel(
    channel_id: str,
    unit: str,
    value_type: Literal["scalar", "vector[3]"],
    origin: Literal["sensor", "derived"],
    semantics: Literal["endpoint", "interval_mean"],
    description: str,
    frame: str | None = None,
) -> ChannelDefinition:
    """Construct a catalog definition with P0 fixed cadence metadata."""
    return ChannelDefinition(
        channel_id=channel_id,
        unit=unit,
        value_type=value_type,
        origin=origin,
        sampling_semantics=semantics,
        resolution=0.0 if origin == "sensor" else None,
        coordinate_frame=frame,
        cadence_s=1,
        description=description,
    )


CHANNELS: tuple[ChannelDefinition, ...] = (
    _channel(
        "orbit.position_itrf_m",
        "m",
        "vector[3]",
        "derived",
        "endpoint",
        "Earth-fixed Cartesian position in metres at the sample time.",
        "ITRS",
    ),
    _channel(
        "orbit.velocity_itrf_m_s",
        "m/s",
        "vector[3]",
        "derived",
        "endpoint",
        "Earth-fixed Cartesian velocity including frame-rotation effects.",
        "ITRS",
    ),
    _channel(
        "orbit.latitude_deg", "deg", "scalar", "derived", "endpoint", "WGS84 geodetic latitude."
    ),
    _channel(
        "orbit.longitude_deg",
        "deg",
        "scalar",
        "derived",
        "endpoint",
        "East-positive longitude in [-180, 180).",
    ),
    _channel(
        "orbit.altitude_m",
        "m",
        "scalar",
        "derived",
        "endpoint",
        "WGS84 ellipsoidal height; not terrain or spherical radial altitude.",
    ),
    _channel(
        "environment.illumination_fraction",
        "1",
        "scalar",
        "derived",
        "endpoint",
        "Fraction of the solar disk visible to the spacecraft.",
    ),
    _channel(
        "environment.panel_incidence_cosine",
        "1",
        "scalar",
        "derived",
        "endpoint",
        "Sunward cosine for the equivalent solar array.",
    ),
    _channel(
        "eps.solar_power_w",
        "W",
        "scalar",
        "sensor",
        "interval_mean",
        "Solar generation delivered to the bus over the sample window.",
    ),
    _channel(
        "eps.load_requested_w",
        "W",
        "scalar",
        "derived",
        "interval_mean",
        "Requested load over the sample window for its interval mode.",
    ),
    _channel(
        "eps.load_served_w",
        "W",
        "scalar",
        "sensor",
        "interval_mean",
        "Load actually supplied over the sample window.",
    ),
    _channel(
        "eps.battery_power_w",
        "W",
        "scalar",
        "sensor",
        "interval_mean",
        "Positive when discharging into the bus; negative when charging.",
    ),
    _channel(
        "eps.battery_energy_wh",
        "Wh",
        "scalar",
        "derived",
        "endpoint",
        "Ideal onboard energy estimate at the sample time.",
    ),
    _channel(
        "eps.battery_soc",
        "1",
        "scalar",
        "derived",
        "endpoint",
        "Stored energy divided by fixed usable capacity.",
    ),
    _channel(
        "eps.curtailed_power_w",
        "W",
        "scalar",
        "derived",
        "interval_mean",
        "Generation not used by loads or battery charging over the window.",
    ),
    _channel(
        "eps.unserved_power_w",
        "W",
        "scalar",
        "derived",
        "interval_mean",
        "Requested load not supplied over the sample window.",
    ),
)

CHANNELS_BY_ID = {channel.channel_id: channel for channel in CHANNELS}


__all__ = ["CHANNELS", "CHANNELS_BY_ID", "ChannelDefinition"]
