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
from metis_sim.domain.subsystems import HousekeepingConfiguration
from metis_sim.models.operations import resolve_operations

MAX_SAFE_INTEGER = 9_007_199_254_740_991
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$", re.ASCII)
SatelliteMode = Literal["nominal", "payload_active", "safe"]


class ContractModel(BaseModel):
    """Base for strict, immutable operator configuration models.

    Notes
    -----
    Subclasses reject unknown fields, freeze validated values, require strict
    types, and reject non-finite floating-point values.
    """

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
    """Simulation timing, seed, and versioned model selections.

    Attributes
    ----------
    epoch_utc : datetime
        UTC-normalized instant at which the run starts.
    duration_s : int
        Configured elapsed duration in simulated seconds; samples include
        both tick zero and the endpoint.
    tick_s, telemetry_period_s : int
        Fixed physical and telemetry cadence; both are one second in P0.
    speed : int
        Requested wall-clock multiplier.
    seed : int
        Reproducibility seed within JavaScript's exact integer range.
    earth_model, orbit_model, sun_model : str
        Versioned model identifiers used by the run.
    environment_source : str or None
        Public name of recorded data that shaped the simulated environment,
        such as ``BUPT-1 solar harvest, 21 June 2023 (scaled)``. It names a
        source only; scenario values stay private.
    """

    epoch_utc: datetime
    duration_s: Annotated[int, Field(ge=1, le=86_400)] = 21_600
    tick_s: Literal[1]
    telemetry_period_s: Literal[1]
    speed: Annotated[int, Field(ge=1, strict=True)] = 90
    seed: Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
    earth_model: Literal["wgs84_j2_v1"]
    orbit_model: Literal["j2_cartesian"]
    sun_model: Literal["astropy_builtin"]
    environment_source: Annotated[str, Field(min_length=1, max_length=160)] | None = None

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
    """Supported panel pointing policy.

    Attributes
    ----------
    type : str
        P0 panel policy, currently ``ideal_sun_tracking``.
    """

    type: Literal["ideal_sun_tracking"]


class PanelConfiguration(ContractModel):
    """Equivalent solar-array nameplate and conversion parameters.

    Attributes
    ----------
    area_m2 : float
        Equivalent panel area in square metres.
    efficiency, conversion_efficiency : float
        Panel and bus-conversion efficiencies in ``(0, 1]``.
    irradiance_1au_w_m2 : float
        Reference solar irradiance in watts per square metre.
    pointing : PointingConfiguration
        Declared panel pointing policy.
    """

    area_m2: Annotated[float, Field(gt=0)]
    efficiency: Annotated[float, Field(gt=0, le=1)]
    conversion_efficiency: Annotated[float, Field(gt=0, le=1)]
    irradiance_1au_w_m2: Annotated[float, Field(ge=1361.0, le=1361.0)]
    pointing: PointingConfiguration


class BatteryConfiguration(ContractModel):
    """Ideal bounded energy-store nameplate and starting condition.

    Attributes
    ----------
    type : str
        P0 battery model, currently ``energy_store``.
    usable_capacity_wh : float
        Fixed usable energy capacity in watt-hours.
    initial_soc : float
        Initial state of charge as a fraction of usable capacity.
    charge_efficiency, discharge_efficiency : float
        Energy conversion efficiencies in ``(0, 1]``.
    max_charge_w, max_discharge_w : float
        Bus-power limits in watts.
    """

    type: Literal["energy_store"]
    usable_capacity_wh: Annotated[float, Field(gt=0)]
    initial_soc: Annotated[float, Field(ge=0, le=1)]
    charge_efficiency: Annotated[float, Field(gt=0, le=1)]
    discharge_efficiency: Annotated[float, Field(gt=0, le=1)]
    max_charge_w: Annotated[float, Field(ge=0)]
    max_discharge_w: Annotated[float, Field(ge=0)]


class NoiseConfiguration(ContractModel):
    """Supported sensor noise selection.

    Attributes
    ----------
    type : str
        P0 uses ``none`` so numerical evidence remains deterministic.
    """

    type: Literal["none"]


class SensorConfiguration(ContractModel):
    """Public channel catalog and sensor-noise policy.

    Attributes
    ----------
    catalog : str
        Versioned public channel catalog identifier.
    noise : NoiseConfiguration
        Noise policy applied after the physical calculation.
    """

    catalog: Literal["power-leo.v1", "spacecraft.v1"]
    noise: NoiseConfiguration


class ConfiguredPublicLimit(ContractModel):
    """Observable SOC threshold with explicit hysteresis.

    Attributes
    ----------
    channel_id : str
        Public channel monitored by the limit, currently battery SOC.
    operator : {"lt", "gt"}
        Comparison used to enter the limit.
    value, clear_value : float
        Entry and hysteresis-clear thresholds as SOC fractions.
    """

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
    """Reusable spacecraft subsystem configuration.

    Attributes
    ----------
    panel : PanelConfiguration
        Equivalent solar-array model.
    battery : BatteryConfiguration
        Bounded energy-store model.
    loads_w : mapping
        Requested load in watts for every supported satellite mode.
    sensors : SensorConfiguration
        Public channel catalog and sensor policy.
    public_limits : tuple of ConfiguredPublicLimit
        Limits that may appear in the public spacecraft descriptor.
    """

    panel: PanelConfiguration
    battery: BatteryConfiguration
    loads_w: dict[SatelliteMode, Annotated[float, Field(ge=0)]]
    sensors: SensorConfiguration
    public_limits: tuple[ConfiguredPublicLimit, ...] = ()
    housekeeping: HousekeepingConfiguration | None = None

    @model_validator(mode="after")
    def validate_housekeeping(self) -> SpacecraftProfile:
        """Keep catalog selection and the modeled payload power budget consistent.

        Returns
        -------
        SpacecraftProfile
            This immutable, internally consistent spacecraft profile.
        """
        extended = self.sensors.catalog == "spacecraft.v1"
        if extended != (self.housekeeping is not None):
            raise ValueError("spacecraft.v1 requires housekeeping; power-leo.v1 excludes it")
        if (
            self.housekeeping
            and self.housekeeping.payload.active_power_w > self.loads_w["payload_active"]
        ):
            raise ValueError("payload active power must fit within the payload_active mode load")
        return self

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
    """Osculating classical orbit elements at the run epoch.

    Attributes
    ----------
    a_m : float
        Semi-major axis in metres.
    e : float
        Dimensionless eccentricity.
    i_deg, raan_deg, argp_deg, true_anomaly_deg : float
        Inclination, right ascension of ascending node, argument of
        periapsis, and true anomaly in degrees.

    Notes
    -----
    The model validates the initial perigee and apogee against the supported
    300--1500 km P0 radial envelope.
    """

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
    """Half-open scheduled operational mode interval.

    Attributes
    ----------
    start_s, end_s : int
        Simulated-second bounds of the half-open interval ``[start_s, end_s)``.
    mode : SatelliteMode
        Mode active during the interval.
    repeat : {"orbit"} or None
        Repeat at the satellite's nominal orbital period, or run once when
        omitted. Every repetition preserves ``end_s - start_s`` seconds.
    added_load_w : float, default=0.0
        Electrical load in watts added to the mode's profile load while the
        interval is active, for tasks such as a capture, a downlink, or a
        compute batch.
    label : str or None
        Optional public task identifier, for example ``downlink``.
    min_start_soc : float or None
        Onboard start guard. When the battery state of charge at the window's
        start tick is below this value, the spacecraft skips the whole window:
        it stays in its initial mode with no added load and reports an
        ``operation_skipped`` event. The guard is checked only at the start.
    """

    start_s: Annotated[int, Field(ge=0, le=86_400)]
    end_s: Annotated[int, Field(ge=1, le=86_400)]
    mode: SatelliteMode
    repeat: Literal["orbit"] | None = None
    added_load_w: Annotated[float, Field(ge=0, le=10_000)] = 0.0
    label: str | None = None
    min_start_soc: Annotated[float, Field(ge=0, le=1)] | None = None

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str | None) -> str | None:
        """Apply the public ASCII identifier grammar to task labels."""
        return None if value is None else _check_identifier(value)

    @model_validator(mode="after")
    def validate_interval(self) -> Operation:
        """Require a non-empty ``[start_s, end_s)`` interval."""
        if self.start_s >= self.end_s:
            raise ValueError("operation end_s must be greater than start_s")
        return self


class VisualConfiguration(ContractModel):
    """Allowlisted visual marker metadata for a spacecraft.

    Attributes
    ----------
    color : str
        Six-digit hexadecimal marker color.
    asset_id : str or None
        Optional identifier resolved by the allowlisted visual asset catalog.
    """

    color: Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")] = "#8FD3FF"
    asset_id: Annotated[str, Field(pattern=ID_PATTERN.pattern)] | None = None


class SatelliteDefinition(ContractModel):
    """Stable spacecraft identity, orbit, profile reference, and schedule.

    Attributes
    ----------
    satellite_id : str
        Stable ASCII identity used in streams and public frames.
    name : str
        Human-readable spacecraft name.
    profile_id : str
        Reference to a reusable :class:`SpacecraftProfile`.
    orbit : OrbitConfiguration
        Initial osculating orbit.
    initial_mode : SatelliteMode
        Default mode whenever no scheduled operation is active, including
        tick zero unless an operation starts there.
    operations : tuple of Operation
        Non-overlapping scheduled mode intervals.
    visual : VisualConfiguration
        Allowlisted marker metadata.
    """

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
    """Display grouping containing unique satellite identities.

    Attributes
    ----------
    constellation_id : str
        Stable grouping identifier.
    satellite_ids : tuple of str
        Unique member IDs retained in display order.
    """

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
    """Elapsed run time and solar generation multiplier control point.

    Attributes
    ----------
    at_s : int
        Simulated-second location of the control point.
    multiplier : float
        Solar-generation multiplier in ``[0, 1]``.
    """

    at_s: Annotated[int, Field(ge=0, le=86_400)]
    multiplier: Annotated[float, Field(ge=0, le=1)]


class ReserveOutcome(ContractModel):
    """Private state-triggered operational reserve outcome rule.

    Attributes
    ----------
    type : str
        P0 outcome type, currently ``energy_reserve_violation``.
    reserve_soc : float
        SOC threshold used by the private evaluator.
    dwell_s : int
        Consecutive simulated seconds required below the threshold.
    """

    type: Literal["energy_reserve_violation"]
    reserve_soc: Annotated[float, Field(gt=0, lt=1)]
    dwell_s: Annotated[int, Field(ge=1)] = 60


class SolarDeratingScenario(ContractModel):
    """Private piecewise-linear solar derating scenario.

    Attributes
    ----------
    satellite_id : str
        Spacecraft affected by the scenario.
    type : str
        P0 scenario type, currently ``solar_derating``.
    points : tuple of DeratingPoint
        Strictly increasing multiplier control points.
    outcome : ReserveOutcome
        Private state-based outcome rule.
    """

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
    """Complete validated P0 simulation input configuration.

    Attributes
    ----------
    schema_version : str
        Configuration contract revision, currently ``simulation.v1``.
    run : RunConfiguration
        Timing, seed, and selected model versions.
    profiles : mapping of str to SpacecraftProfile
        Reusable spacecraft subsystem definitions.
    satellites : tuple of SatelliteDefinition
        One to ten configured spacecraft.
    constellations : tuple of ConstellationDefinition
        Optional display groupings with validated membership.
    scenario : tuple of SolarDeratingScenario
        Private derating scenarios, at most one per spacecraft.

    Notes
    -----
    Cross-object references and nested mappings are validated and frozen
    before the configuration is normalized or hashed.
    """

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
                if (
                    operation.added_load_w > 0
                    and self.profiles[satellite.profile_id].housekeeping is not None
                ):
                    raise ValueError(
                        "added_load_w is not supported with spacecraft.v1 housekeeping profiles"
                    )
            resolve_operations(satellite.operations, self.run.duration_s, satellite.orbit.a_m)
        constellation_ids = [item.constellation_id for item in self.constellations]
        if len(constellation_ids) != len(set(constellation_ids)):
            raise ValueError("constellation_id values must be unique")
        for constellation in self.constellations:
            unknown = set(constellation.satellite_ids) - satellite_id_set
            if unknown:
                raise ValueError(f"unknown constellation satellite IDs: {sorted(unknown)}")
        scenario_ids = [item.satellite_id for item in self.scenario]
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("at most one solar_derating scenario per satellite_id")
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
