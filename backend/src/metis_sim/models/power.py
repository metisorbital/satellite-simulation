"""Conservative, energy-limited bus allocation and battery integration."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class PowerAllocation:
    """One interval's complete bus-power and stored-energy ledger.

    Attributes
    ----------
    battery_power_w : float
        Positive for bus discharge, negative for charging.
    energy_wh : float
        Stored battery energy after this interval.
    charge_w, discharge_w : float
        Nonnegative interval-average allocations before battery efficiency.
    """

    generation_w: float
    requested_w: float
    served_w: float
    charge_w: float
    discharge_w: float
    curtailed_w: float
    unserved_w: float
    battery_power_w: float
    energy_wh: float


def allocate_power(
    generation_w: float,
    requested_w: float,
    energy_wh: float,
    capacity_wh: float,
    charge_efficiency: float,
    discharge_efficiency: float,
    max_charge_w: float,
    max_discharge_w: float,
    dt_s: float,
) -> PowerAllocation:
    """Allocate bounded bus power without creating energy by SOC clipping.

    Parameters
    ----------
    generation_w, requested_w : float
        Nonnegative available generation and requested load in watts.
    energy_wh, capacity_wh : float
        Previous stored energy and fixed usable capacity in watt-hours.
    charge_efficiency, discharge_efficiency : float
        Energy conversion efficiencies in (0,1].
    max_charge_w, max_discharge_w : float
        Bus power caps in watts.
    dt_s : float
        Interval seconds, or zero for initial instantaneous allocation.

    Returns
    -------
    PowerAllocation
        Served/curtailed/unserved powers and conserved endpoint energy.

    Notes
    -----
    When the battery reaches a bound during an interval, the returned
    energy-limited average power includes the remaining time at that bound.
    Zero duration never evaluates a formula containing division by time.
    """
    values = (
        generation_w,
        requested_w,
        energy_wh,
        capacity_wh,
        charge_efficiency,
        discharge_efficiency,
        max_charge_w,
        max_discharge_w,
        dt_s,
    )
    if not all(isfinite(value) for value in values):
        raise ValueError("Power inputs must be finite.")
    if (
        min(generation_w, requested_w, energy_wh, max_charge_w, max_discharge_w, dt_s) < 0
        or capacity_wh <= 0
        or energy_wh > capacity_wh
        or not 0 < charge_efficiency <= 1
        or not 0 < discharge_efficiency <= 1
    ):
        raise ValueError("Power inputs violate battery bounds or efficiency limits.")
    charge = discharge = curtailed = unserved = 0.0
    hours = dt_s / 3600.0
    if generation_w >= requested_w:
        if energy_wh < capacity_wh:
            charge = min(generation_w - requested_w, max_charge_w)
            if dt_s:
                charge = min(charge, (capacity_wh - energy_wh) / (charge_efficiency * hours))
        served = requested_w
        curtailed = generation_w - requested_w - charge
    else:
        if energy_wh > 0:
            discharge = min(requested_w - generation_w, max_discharge_w)
            if dt_s:
                discharge = min(discharge, energy_wh * discharge_efficiency / hours)
        served = generation_w + discharge
        unserved = requested_w - served
    next_energy = (
        energy_wh + charge_efficiency * charge * hours - discharge * hours / discharge_efficiency
    )
    # Energy was constrained before integration. These guard only sub-ULP
    # subtraction at an exactly full/empty boundary, not unlimited demand.
    if -1e-12 <= next_energy < 0:
        next_energy = 0.0
    if capacity_wh < next_energy <= capacity_wh + 1e-12:
        next_energy = capacity_wh
    return PowerAllocation(
        generation_w,
        requested_w,
        served,
        charge,
        discharge,
        curtailed,
        unserved,
        discharge - charge,
        next_energy,
    )
