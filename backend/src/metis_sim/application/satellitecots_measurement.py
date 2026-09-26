"""Allowlisted unit conversion of recorded BUPT-1 source readings."""

import math
from collections.abc import Mapping

from metis_sim.domain.satellitecots_catalog import SOURCE_CHANNELS
from metis_sim.domain.telemetry import ChannelReading


def project_satellitecots_channels(
    values: Mapping[str, float | None],
) -> dict[str, ChannelReading]:
    """Convert source readings without resampling, filling, or model inference.

    Parameters
    ----------
    values : mapping of str to float or None
        Raw source-column values for one original CSV row. Missing numeric
        cells remain null; all required source columns must be present.

    Returns
    -------
    dict of str to ChannelReading
        SI sensor readings and explicitly declared snapshot derivations.
        Missing inputs yield missing derived readings; impossible negative
        total power yields an invalid reading, without clipping the source.
    """
    result: dict[str, ChannelReading] = {}
    for column, (channel, _, scale, _, _) in SOURCE_CHANNELS.items():
        value = values[column]
        result[channel] = _reading(None if value is None else value * scale)
    solar_current = _sum(values["MPPT1_Iout"], values["MPPT2_Iout"])
    result["eps.solar_current_a"] = _reading(
        None if solar_current is None else solar_current / 1000
    )
    result["eps.solar_power_w"] = _reading(
        _power(solar_current, values["Total_U"]), nonnegative=True
    )
    result["eps.load_served_w"] = _reading(
        _power(values["Total_I"], values["Total_U"]), nonnegative=True
    )
    return result


def _reading(value: float | None, *, nonnegative: bool = False) -> ChannelReading:
    if value is None:
        return ChannelReading(value=None, quality="missing")
    if not math.isfinite(value) or (nonnegative and value < 0):
        return ChannelReading(value=None, quality="invalid")
    return ChannelReading(value=float(value), quality="valid")


def _sum(first: float | None, second: float | None) -> float | None:
    return None if first is None or second is None else first + second


def _power(current_ma: float | None, voltage_mv: float | None) -> float | None:
    return None if current_ma is None or voltage_mv is None else current_ma * voltage_mv / 1e6
