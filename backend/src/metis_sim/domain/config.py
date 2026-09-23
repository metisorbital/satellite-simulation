"""Validated immutable configuration contracts for the Metis simulation.

All configuration entering the simulator is parsed through these models before
normalization or hashing. The models intentionally mirror the public YAML
contract so configuration remains data rather than an import mechanism.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from metis_sim.domain.immutable import FrozenDict

MAX_SAFE_INTEGER = 9_007_199_254_740_991
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$", re.ASCII)
SatelliteMode = Literal["nominal", "payload_active", "safe"]


class ContractModel(BaseModel):
    """Base for strict, immutable operator configuration models."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


def _check_identifier(value: str) -> str:
    """Validate an ASCII contract identifier.

    Parameters
    ----------
    value : str
        Identifier to validate.

    Returns
    -------
    str
        The original identifier.
    """
    if not ID_PATTERN.fullmatch(value):
        raise ValueError("must match ASCII [A-Za-z0-9_-]{1,64}")
    return value


class RunConfiguration(ContractModel):
    """Simulation timing, seed, and versioned model selections."""

    epoch_utc: datetime
    duration_s: Annotated[int, Field(ge=1, le=86_400)] = 21_600
    tick_s: Literal[1]
    telemetry_period_s: Literal[1]
    speed: Literal[1, 5, 20] = 20
    seed: Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
    earth_model: Literal["wgs84_j2_v1"]
    orbit_model: Literal["j2_cartesian"]
    sun_model: Literal["astropy_builtin"]

    @field_validator("epoch_utc")
    @classmethod
    def require_utc_offset(cls, value: datetime) -> datetime:
        """Require an explicit UTC offset and canonicalize the epoch to UTC.

        Parameters
        ----------
        value : datetime
            Parsed run epoch.

        Returns
        -------
        datetime
            Epoch converted to UTC.
        """
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("epoch_utc must include a UTC offset")
        return value.astimezone(UTC)


class PointingConfiguration(ContractModel):
    """Supported panel pointing policy."""

    type: Literal["ideal_sun_tracking"]


class PanelConfiguration(ContractModel):
    """Equivalent solar-array nameplate and conversion parameters."""

    area_m2: Annotated[float, Field(gt=0)]
    efficiency: Annotated[float, Field(gt=0, le=1)]
    conversion_efficiency: Annotated[float, Field(gt=0, le=1)]
    irradiance_1au_w_m2: Annotated[float, Field(ge=1361.0, le=1361.0)]
    pointing: PointingConfiguration


class BatteryConfiguration(ContractModel):
    """Ideal bounded energy-store nameplate and starting condition."""

    type: Literal["energy_store"]
    usable_capacity_wh: Annotated[float, Field(gt=0)]
    initial_soc: Annotated[float, Field(ge=0, le=1)]
    charge_efficiency: Annotated[float, Field(gt=0, le=1)]
    discharge_efficiency: Annotated[float, Field(gt=0, le=1)]
    max_charge_w: Annotated[float, Field(ge=0)]
    max_discharge_w: Annotated[float, Field(ge=0)]


class NoiseConfiguration(ContractModel):
    """Supported sensor noise selection."""

    type: Literal["none"]


class SensorConfiguration(ContractModel):
    """Public channel catalog and sensor-noise policy."""

    catalog: Literal["power-leo.v1"]
    noise: NoiseConfiguration


class ConfiguredPublicLimit(ContractModel):
    """Observable SOC threshold with explicit hysteresis."""

    channel_id: Literal["eps.battery_soc"]
    operator: Literal["lt", "gt"]
    value: Annotated[float, Field(ge=0, le=1)]
    clear_value: Annotated[float, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_hysteresis(self) -> ConfiguredPublicLimit:
        """Ensure the clear threshold is on the hysteretic side of entry."""
        if self.operator == "lt" and self.clear_value < self.value:
            raise ValueError("clear_value must be >= value for lt limits")
        if self.operator == "gt" and self.clear_value > self.value:
            raise ValueError("clear_value must be <= value for gt limits")
        return self


class SpacecraftProfile(ContractModel):
    """Reusable spacecraft subsystem configuration."""

    panel: PanelConfiguration
    battery: BatteryConfiguration
    loads_w: dict[SatelliteMode, Annotated[float, Field(ge=0)]]
    sensors: SensorConfiguration
    public_limits: tuple[ConfiguredPublicLimit, ...] = ()

    @field_validator("loads_w", mode="before")
    @classmethod
    def require_complete_load_modes(cls, value: object) -> object:
        """Require loads for all P0 operational modes.

        Parameters
        ----------
        value : object
            Input load table.

        Returns
        -------
        object
            Original table after completeness validation.
        """
        required = {"nominal", "payload_active", "safe"}
        if not isinstance(value, dict) or set(value) != required:
            raise ValueError("loads_w must define nominal, payload_active, and safe")
        return value

    @field_validator("loads_w", mode="after")
    @classmethod
    def freeze_loads(cls, value: dict[str, float]) -> FrozenDict:
        """Prevent mutation of the validated load table."""
        return FrozenDict(value)


class OrbitConfiguration(ContractModel):
    """Osculating classical orbit elements at the run epoch."""

    a_m: Annotated[float, Field(gt=0)]
    e: Annotated[float, Field(ge=0, le=0.05)]
    i_deg: Annotated[float, Field(ge=0, le=180)]
    raan_deg: Annotated[float, Field(ge=0, lt=360)]
    argp_deg: Annotated[float, Field(ge=0, lt=360)]
    true_anomaly_deg: Annotated[float, Field(ge=0, lt=360)]

    @model_validator(mode="after")
    def validate_altitude_envelope(self) -> OrbitConfiguration:
        """Keep initial osculating perigee and apogee in the P0 LEO envelope."""
        earth_radius_m = 6_378_137.0
        perigee_altitude = self.a_m * (1.0 - self.e) - earth_radius_m
        apogee_altitude = self.a_m * (1.0 + self.e) - earth_radius_m
        if perigee_altitude < 300_000.0:
            raise ValueError("osculating perigee altitude must be >= 300 km")
        if apogee_altitude > 1_500_000.0:
            raise ValueError("osculating apogee altitude must be <= 1500 km")
        if self.e <= 1e-12 and self.argp_deg != 0:
            raise ValueError("argp_deg must be 0 for circular orbits")
        if abs(math.sin(math.radians(self.i_deg))) <= 1e-12 and self.raan_deg != 0:
            raise ValueError("raan_deg must be 0 for equatorial orbits")
        return self


class Operation(ContractModel):
    """Half-open scheduled operational mode interval."""

    start_s: Annotated[int, Field(ge=0, le=86_400)]
    end_s: Annotated[int, Field(ge=1, le=86_400)]
    mode: SatelliteMode

    @model_validator(mode="after")
    def validate_interval(self) -> Operation:
        """Require a non-empty ``[start_s, end_s)`` interval."""
        if self.start_s >= self.end_s:
            raise ValueError("operation end_s must be greater than start_s")
        return self


class VisualConfiguration(ContractModel):
    """Allowlisted visual marker metadata for a spacecraft."""

    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")] = "#8FD3FF"
    asset_id: Annotated[str, Field(pattern=ID_PATTERN.pattern)] | None = None


class SatelliteDefinition(ContractModel):
    """Stable spacecraft identity, orbit, profile reference, and schedule."""

    satellite_id: str
    name: Annotated[str, Field(min_length=1, max_length=128)]
    profile_id: str
    orbit: OrbitConfiguration
    initial_mode: SatelliteMode
    operations: tuple[Operation, ...]
    visual: VisualConfiguration = Field(default_factory=VisualConfiguration)

    @field_validator("satellite_id", "profile_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        """Apply the public ASCII identifier grammar."""
        return _check_identifier(value)

    @model_validator(mode="after")
    def validate_schedule(self) -> SatelliteDefinition:
        """Reject overlapping operations on this spacecraft."""
        ordered = sorted(self.operations, key=lambda op: (op.start_s, op.end_s))
        for previous, current in zip(ordered, ordered[1:], strict=False):
            if current.start_s < previous.end_s:
                raise ValueError("operations must not overlap")
        return self


class ConstellationDefinition(ContractModel):
    """Display grouping containing unique satellite identities."""

    constellation_id: str
    satellite_ids: tuple[str, ...]

    @field_validator("constellation_id")
    @classmethod
    def validate_constellation_id(cls, value: str) -> str:
        """Apply the public ASCII identifier grammar."""
        return _check_identifier(value)

    @field_validator("satellite_ids")
    @classmethod
    def validate_member_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Validate unique member IDs without changing display order."""
        for item in value:
            _check_identifier(item)
        if len(set(value)) != len(value):
            raise ValueError("satellite_ids must be unique")
        return value


class DeratingPoint(ContractModel):
    """Elapsed run time and solar generation multiplier control point."""

    at_s: Annotated[int, Field(ge=0, le=86_400)]
    multiplier: Annotated[float, Field(ge=0, le=1)]


class ReserveOutcome(ContractModel):
    """Private state-triggered operational reserve outcome rule."""

    type: Literal["energy_reserve_violation"]
    reserve_soc: Annotated[float, Field(gt=0, lt=1)]
    dwell_s: Annotated[int, Field(ge=1)] = 60


class SolarDeratingScenario(ContractModel):
    """Private piecewise-linear solar derating scenario."""

    satellite_id: str
    type: Literal["solar_derating"]
    points: tuple[DeratingPoint, ...]
    outcome: ReserveOutcome

    @field_validator("satellite_id")
    @classmethod
    def validate_satellite_id(cls, value: str) -> str:
        """Apply the public ASCII identifier grammar."""
        return _check_identifier(value)

    @model_validator(mode="after")
    def validate_ordered_points(self) -> SolarDeratingScenario:
        """Require increasing control-point times."""
        if any(b.at_s <= a.at_s for a, b in zip(self.points, self.points[1:], strict=False)):
            raise ValueError("scenario point times must be strictly increasing")
        return self


class SimulationConfig(ContractModel):
    """Complete validated P0 simulation input configuration."""

    schema_version: Literal["simulation.v1"]
    run: RunConfiguration
    profiles: dict[str, SpacecraftProfile]
    satellites: tuple[SatelliteDefinition, ...]
    constellations: tuple[ConstellationDefinition, ...]
    scenario: tuple[SolarDeratingScenario, ...]

    @field_validator("profiles", mode="after")
    @classmethod
    def freeze_profiles(cls, value: dict[str, SpacecraftProfile]) -> FrozenDict:
        """Prevent profiles from changing after whole-config validation."""
        return FrozenDict(value)

    @model_validator(mode="after")
    def validate_references_and_bounds(self) -> SimulationConfig:
        """Validate cross-object references and P0 cardinality constraints."""
        if not self.profiles:
            raise ValueError("profiles must contain at least one profile")
        for profile_id in self.profiles:
            _check_identifier(profile_id)
        satellite_ids = [sat.satellite_id for sat in self.satellites]
        if not 1 <= len(satellite_ids) <= 10:
            raise ValueError("satellites must contain between 1 and 10 entries")
        if len(satellite_ids) != len(set(satellite_ids)):
            raise ValueError("satellite_id values must be unique")
        satellite_id_set = set(satellite_ids)
        for satellite in self.satellites:
            if satellite.profile_id not in self.profiles:
                raise ValueError(f"unknown profile_id: {satellite.profile_id}")
            for operation in satellite.operations:
                if operation.end_s > self.run.duration_s:
                    raise ValueError("operation interval must be within run.duration_s")
        constellation_ids = [item.constellation_id for item in self.constellations]
        if len(constellation_ids) != len(set(constellation_ids)):
            raise ValueError("constellation_id values must be unique")
        for constellation in self.constellations:
            unknown = set(constellation.satellite_ids) - satellite_id_set
            if unknown:
                raise ValueError(f"unknown constellation satellite IDs: {sorted(unknown)}")
        if len(self.scenario) > 1:
            raise ValueError("P0 supports at most one solar_derating scenario")
        for scenario in self.scenario:
            if scenario.satellite_id not in satellite_id_set:
                raise ValueError(f"unknown scenario satellite_id: {scenario.satellite_id}")
            if not scenario.points:
                raise ValueError("solar_derating scenario requires at least one point")
            for point in scenario.points:
                if point.at_s > self.run.duration_s:
                    raise ValueError("scenario point must be within run.duration_s")
        return self


__all__ = [
    "BatteryConfiguration",
    "ConstellationDefinition",
    "Operation",
    "OrbitConfiguration",
    "PanelConfiguration",
    "ConfiguredPublicLimit",
    "RunConfiguration",
    "SatelliteDefinition",
    "SimulationConfig",
    "SolarDeratingScenario",
    "SpacecraftProfile",
    "VisualConfiguration",
]
