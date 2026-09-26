"""Conservative fixed-step conduction and radiation for three thermal nodes."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from metis_sim.domain.subsystems import ThermalConfiguration

STEFAN_BOLTZMANN_W_M2_K4 = 5.670374419e-8


@dataclass(frozen=True, slots=True)
class ThermalSample:
    """Endpoint temperatures with an independently checkable heat ledger.

    Attributes
    ----------
    temperature_k : tuple of float
        Battery, avionics bus, and payload temperatures in kelvin.
    absorbed_solar_w, dissipated_w, radiated_w : float
        Network totals at the start of this explicit integration interval.
    energy_change_j : float
        Actual total heat-capacity-weighted temperature change.
    """

    temperature_k: tuple[float, float, float]
    absorbed_solar_w: float
    dissipated_w: float
    radiated_w: float
    energy_change_j: float


class ThermalModel:
    """Integrate a bounded three-node thermal network at fixed one-second steps.

    Parameters
    ----------
    config : ThermalConfiguration
        Immutable node surfaces, capacities, links, and initial temperatures.

    Notes
    -----
    Forward Euler conserves the discrete heat ledger exactly; symmetric
    internal conduction cancels in its network sum. Within 100--500 K the
    validated coefficients bound every loss/conduction rate below 0.5/s,
    keeping the one-second update stable. Leaving the envelope is an error,
    never a temperature clamp. There is no Earth IR, albedo, or thermostat.
    """

    def __init__(self, config: ThermalConfiguration) -> None:
        nodes = (config.battery, config.bus, config.payload)
        self._temperature = np.array([node.initial_temperature_k for node in nodes])
        self._capacity = np.array([node.heat_capacity_j_k for node in nodes])
        self._solar_area = np.array([node.solar_area_m2 * node.absorptivity for node in nodes])
        self._radiation = np.array(
            [node.radiating_area_m2 * node.emissivity * STEFAN_BOLTZMANN_W_M2_K4 for node in nodes]
        )
        self._sink_fourth = config.sink_temperature_k**4
        self._battery_link = config.battery_bus_conductance_w_k
        self._payload_link = config.payload_bus_conductance_w_k

    def step(
        self,
        dt_s: float,
        solar_flux_w_m2: float,
        dissipation_w: tuple[float, float, float],
    ) -> ThermalSample:
        """Advance from actual electrical heat and eclipse-dependent sunlight.

        Parameters
        ----------
        dt_s : float
            Zero for initial measurement or exactly one simulated second.
        solar_flux_w_m2 : float
            Incident solar flux after distance and eclipse attenuation.
        dissipation_w : tuple of float
            Nonnegative battery-converter, avionics, and payload heat powers.

        Returns
        -------
        ThermalSample
            Endpoint temperatures and completed-interval network heat ledger.

        Raises
        ------
        ValueError
            Inputs are invalid or the physical state leaves 100--500 K.
        """
        if dt_s not in (0.0, 1.0):
            raise ValueError("Thermal dt_s must be zero or one second.")
        if not math.isfinite(solar_flux_w_m2) or solar_flux_w_m2 < 0:
            raise ValueError("Solar flux must be finite and nonnegative.")
        heat = np.asarray(dissipation_w, dtype=np.float64)
        if heat.shape != (3,) or not np.all(np.isfinite(heat)) or np.any(heat < 0):
            raise ValueError("Thermal dissipation requires three nonnegative finite powers.")
        solar = self._solar_area * solar_flux_w_m2
        radiation = self._radiation * (self._temperature**4 - self._sink_fourth)
        battery_to_bus = self._battery_link * (self._temperature[0] - self._temperature[1])
        payload_to_bus = self._payload_link * (self._temperature[2] - self._temperature[1])
        conduction = np.array([-battery_to_bus, battery_to_bus + payload_to_bus, -payload_to_bus])
        updated = (
            self._temperature + dt_s * (heat + solar - radiation + conduction) / self._capacity
        )
        if not np.all(np.isfinite(updated)) or np.any(updated < 100) or np.any(updated > 500):
            raise ValueError("Thermal state left the supported 100--500 K envelope.")
        energy_change = float(np.dot(updated - self._temperature, self._capacity))
        self._temperature = updated
        return ThermalSample(
            temperature_k=(float(updated[0]), float(updated[1]), float(updated[2])),
            absorbed_solar_w=float(solar.sum()),
            dissipated_w=float(heat.sum()),
            radiated_w=float(radiation.sum()),
            energy_change_j=energy_change,
        )
