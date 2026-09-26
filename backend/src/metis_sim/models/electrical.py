"""Ideal circuit measurements consistent with the conserved EPS ledger."""

from __future__ import annotations

from dataclasses import dataclass

from metis_sim.domain.subsystems import ElectricalConfiguration
from metis_sim.models.power import PowerAllocation


@dataclass(frozen=True, slots=True)
class ElectricalSample:
    """Rail values and converter dissipation for one completed interval.

    Attributes
    ----------
    channels : tuple of tuple
        Immutable channel/value pairs, including explicit positive IN/OUT.
    battery_dissipation_w : float
        Charging and discharging converter losses, not additional bus demand.
    """

    channels: tuple[tuple[str, float], ...]
    battery_dissipation_w: float


def electrical_sample(
    config: ElectricalConfiguration,
    allocation: PowerAllocation,
    charge_efficiency: float,
    discharge_efficiency: float,
) -> ElectricalSample:
    """Convert existing branch powers to ideal regulated-rail measurements.

    Parameters
    ----------
    config : ElectricalConfiguration
        Validated constant-voltage circuit parameters.
    allocation : PowerAllocation
        Authoritative bus-power allocation, never recomputed here.
    charge_efficiency, discharge_efficiency : float
        Existing energy-store efficiencies in ``(0, 1]``.

    Returns
    -------
    ElectricalSample
        Terminal currents consistent with ``dE/dt = V * (IN - OUT)`` and
        converter heat equal to the difference between bus and stored power.

    Notes
    -----
    An empty store or inactive branch has zero measured voltage. The model
    omits electrochemical voltage curves, resistance, ripple, and transients.
    """
    if not 0 < charge_efficiency <= 1 or not 0 < discharge_efficiency <= 1:
        raise ValueError("Circuit efficiencies must be in (0, 1].")
    charge_terminal_w = allocation.charge_w * charge_efficiency
    discharge_terminal_w = allocation.discharge_w / discharge_efficiency
    battery_powered = (
        allocation.energy_wh > 0 or allocation.charge_w > 0 or allocation.discharge_w > 0
    )
    return ElectricalSample(
        channels=(
            ("eps.battery_voltage_v", config.battery_voltage_v if battery_powered else 0.0),
            ("eps.battery_current_in_a", charge_terminal_w / config.battery_voltage_v),
            ("eps.battery_current_out_a", discharge_terminal_w / config.battery_voltage_v),
            ("eps.solar_voltage_v", config.solar_voltage_v if allocation.generation_w > 0 else 0.0),
            ("eps.solar_current_a", allocation.generation_w / config.solar_voltage_v),
            ("eps.bus_voltage_v", config.bus_voltage_v if allocation.served_w > 0 else 0.0),
            ("eps.bus_current_a", allocation.served_w / config.bus_voltage_v),
        ),
        battery_dissipation_w=(
            allocation.charge_w - charge_terminal_w + discharge_terminal_w - allocation.discharge_w
        ),
    )
