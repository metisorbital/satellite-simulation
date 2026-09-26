"""Declared synthetic circuit, thermal, and payload model parameters."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from metis_sim.domain.attitude import AttitudeConfiguration


class SubsystemConfiguration(BaseModel):
    """Reject mutable, unknown, non-finite, or implicitly converted inputs.

    Notes
    -----
    These parameters describe a synthetic spacecraft, not a calibration of
    the mission that supplied the telemetry examples.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class ElectricalConfiguration(SubsystemConfiguration):
    """Ideal regulated rails connected to the existing energy ledger.

    Attributes
    ----------
    battery_voltage_v : float
        Constant ideal energy-store terminal voltage; no voltage sag model.
    solar_voltage_v : float
        Constant solar converter output voltage on the generation branch.
    bus_voltage_v : float
        Constant regulated load-bus voltage when load power is supplied.
    """

    battery_voltage_v: Annotated[float, Field(ge=1, le=100)] = 8.2
    solar_voltage_v: Annotated[float, Field(ge=1, le=100)] = 12.0
    bus_voltage_v: Annotated[float, Field(ge=1, le=100)] = 5.0


class ThermalNodeConfiguration(SubsystemConfiguration):
    """One isothermal node with radiation and directly absorbed sunlight.

    Attributes
    ----------
    initial_temperature_k : float
        Initial absolute temperature in kelvin.
    heat_capacity_j_k : float
        Constant lumped thermal capacity in joules per kelvin.
    solar_area_m2, radiating_area_m2 : float
        Effective Sun-facing absorbed area and emitting area, in square metres.
    absorptivity, emissivity : float
        Dimensionless surface coefficients.

    Notes
    -----
    Parameter bounds keep the explicit one-second thermal update stable
    throughout its declared 100--500 K operating envelope.
    """

    initial_temperature_k: Annotated[float, Field(ge=150, le=400)] = 293.15
    heat_capacity_j_k: Annotated[float, Field(ge=100, le=10_000_000)] = 5_000.0
    solar_area_m2: Annotated[float, Field(ge=0, le=1)] = 0.02
    radiating_area_m2: Annotated[float, Field(ge=0, le=1)] = 0.1
    absorptivity: Annotated[float, Field(ge=0, le=1)] = 0.3
    emissivity: Annotated[float, Field(ge=0, le=1)] = 0.8


class ThermalConfiguration(SubsystemConfiguration):
    """Battery, avionics bus, and payload thermal network.

    Attributes
    ----------
    battery, bus, payload : ThermalNodeConfiguration
        Three internally isothermal nodes; all electrical dissipation enters
        its corresponding node.
    battery_bus_conductance_w_k, payload_bus_conductance_w_k : float
        Symmetric conductive links, in watts per kelvin.
    sink_temperature_k : float
        Effective radiative sink; omits explicit Earth IR and albedo.
    """

    battery: ThermalNodeConfiguration = Field(default_factory=ThermalNodeConfiguration)
    bus: ThermalNodeConfiguration = Field(default_factory=ThermalNodeConfiguration)
    payload: ThermalNodeConfiguration = Field(default_factory=ThermalNodeConfiguration)
    battery_bus_conductance_w_k: Annotated[float, Field(ge=0, le=10)] = 1.0
    payload_bus_conductance_w_k: Annotated[float, Field(ge=0, le=10)] = 1.0
    sink_temperature_k: Annotated[float, Field(ge=0, le=100)] = 3.0


class PayloadConfiguration(SubsystemConfiguration):
    """Powered acquisition and finite storage parameters.

    Attributes
    ----------
    active_power_w : float
        Portion of the scheduled ``payload_active`` load allocated to payload.
    image_period_s : int
        Consecutive fully powered active seconds required per image.
    image_size_bytes, storage_capacity_bytes, initial_storage_bytes : int
        Image size, fixed storage capacity, and initially occupied bytes.

    Notes
    -----
    The model has no downlink schedule, compression, deletion, heater, or
    mission-specific camera status encoding. Acquisition stops at capacity.
    """

    active_power_w: Annotated[float, Field(gt=0, le=10_000)] = 20.0
    image_period_s: Annotated[int, Field(ge=1, le=86_400)] = 5
    image_size_bytes: Annotated[int, Field(ge=1, le=1_000_000_000)] = 1_048_576
    storage_capacity_bytes: Annotated[int, Field(ge=1, le=1_000_000_000_000)] = 1_073_741_824
    initial_storage_bytes: Annotated[int, Field(ge=0, le=1_000_000_000_000)] = 0

    @model_validator(mode="after")
    def validate_storage(self) -> PayloadConfiguration:
        """Require initial contents and one complete image to fit the medium.

        Returns
        -------
        PayloadConfiguration
            The validated immutable configuration.
        """
        if self.initial_storage_bytes > self.storage_capacity_bytes:
            raise ValueError("initial_storage_bytes must not exceed storage_capacity_bytes")
        if self.image_size_bytes > self.storage_capacity_bytes:
            raise ValueError("image_size_bytes must not exceed storage_capacity_bytes")
        return self


class HousekeepingConfiguration(SubsystemConfiguration):
    """Opt in to physical housekeeping around the orbit and EPS models.

    Attributes
    ----------
    electrical : ElectricalConfiguration
        Ideal circuit rails used to derive currents from the energy ledger.
    thermal : ThermalConfiguration
        Three-node conduction and radiation network.
    payload : PayloadConfiguration
        Powered camera acquisition and storage model.
    attitude : AttitudeConfiguration
        Ideal nadir body attitude and centered dipole magnetic field.
    """

    electrical: ElectricalConfiguration = Field(default_factory=ElectricalConfiguration)
    thermal: ThermalConfiguration = Field(default_factory=ThermalConfiguration)
    payload: PayloadConfiguration = Field(default_factory=PayloadConfiguration)
    attitude: AttitudeConfiguration = Field(default_factory=AttitudeConfiguration)
