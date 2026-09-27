"""Public telemetry and operational event envelopes."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from metis_sim.domain.catalog import CHANNELS_BY_CATALOG
from metis_sim.domain.immutable import FrozenDict

MAX_SAFE_INTEGER = 9_007_199_254_740_991
ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
Mode = Literal["nominal", "payload_active", "safe"]


class PublicModel(BaseModel):
    """Base for strict immutable public wire models.

    Notes
    -----
    Extra fields and non-finite numbers are rejected so a producer cannot
    publish undeclared or non-portable values.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


def _utc_datetime(value: datetime) -> datetime:
    """Validate explicit offset and return a UTC-normalized timestamp."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a UTC offset")
    return value.astimezone(UTC)


class ChannelReading(PublicModel):
    """One allowlisted channel value and its measurement quality.

    Attributes
    ----------
    value : float, tuple of float, or None
        Scalar, declared string code, or fixed three/four-vector reading.
        Failed readings use ``None``; vector meaning comes from the catalog.
    quality : {"valid", "missing", "invalid", "saturated"}
        Quality state that explains whether ``value`` is usable.

    Notes
    -----
    Valid and saturated readings require a value; missing and invalid
    readings require ``None``.
    """

    value: float | tuple[float, float, float] | tuple[float, float, float, float] | str | None
    quality: Literal["valid", "missing", "invalid", "saturated"]

    @field_validator("value", mode="before")
    @classmethod
    def finite_numeric_value(cls, value: object) -> object:
        """Reject non-finite numeric readings before model validation."""
        values = value if isinstance(value, (list, tuple)) else (value,)
        for item in values:
            if isinstance(item, float) and not math.isfinite(item):
                raise ValueError("channel values must be finite")
        return tuple(value) if isinstance(value, list) else value

    @model_validator(mode="after")
    def validate_quality_value(self) -> ChannelReading:
        """Require null values exactly for failed readings."""
        if self.quality in {"missing", "invalid"} and self.value is not None:
            raise ValueError("missing and invalid readings must have null value")
        if self.quality in {"valid", "saturated"} and self.value is None:
            raise ValueError("valid and saturated readings must have a value")
        return self


class MeasurementFrame(PublicModel):
    """Allowlisted producer-neutral telemetry measurement frame.

    Attributes
    ----------
    schema_version : str
        Breaking-contract identifier, currently ``telemetry.v1``.
    source_id : str
        Stable producer identity.
    stream_id : UUID
        Monotonic sequence namespace for one spacecraft stream.
    sequence : int
        Zero-based stream sequence, bounded by the exact JSON integer range.
    satellite_id : str
        Logical spacecraft identity.
    source_kind : {"synthetic", "observed"}
        Provenance of the producer data.
    time_domain : {"simulation_utc", "mission_utc"}
        Meaning of ``observed_at``.
    observed_at, emitted_at : datetime
        UTC represented sample time and producer emission time.
    sample_window_s : float
        Interval length ending at ``observed_at`` for interval-average
        channels; zero denotes the initial instantaneous frame.
    catalog_version : str
        Versioned channel catalog identifier.
    mode, interval_mode : Mode or None
        Endpoint mode and mode used for interval-average channels.
    channels : mapping of str to ChannelReading
        Allowlisted measured or derived public channel values.

    Notes
    -----
    Timestamps are normalized to UTC and channel mappings are frozen after
    validation. Private scenario parameters, seeds, and future outcomes do
    not belong in this envelope.
    """

    schema_version: Literal["telemetry.v1"]
    source_id: Annotated[str, Field(pattern=ID_PATTERN)]
    stream_id: UUID
    sequence: Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
    satellite_id: Annotated[str, Field(pattern=ID_PATTERN)]
    source_kind: Literal["synthetic", "observed"]
    time_domain: Literal["simulation_utc", "mission_utc"]
    observed_at: datetime
    sample_window_s: Annotated[float, Field(ge=0)]
    emitted_at: datetime
    catalog_version: Literal["power-leo.v1", "spacecraft.v1", "satellitecots.v1"]
    mode: Mode | None
    interval_mode: Mode | None
    channels: dict[str, ChannelReading]

    @field_validator("channels", mode="after")
    @classmethod
    def freeze_channels(cls, value: dict[str, ChannelReading]) -> FrozenDict:
        """Prevent changes to channel values after frame validation."""
        return FrozenDict(value)

    @field_validator("observed_at", "emitted_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        """Require RFC 3339 offsets and normalize timestamps to UTC."""
        return _utc_datetime(value)

    @model_validator(mode="after")
    def validate_channels_against_catalog(self) -> MeasurementFrame:
        """Enforce catalog membership and scalar/vector channel types."""
        if self.source_kind == "synthetic" and self.mode is None:
            raise ValueError("synthetic telemetry requires its modeled operating mode")
        for channel_id, reading in self.channels.items():
            definition = CHANNELS_BY_CATALOG[self.catalog_version].get(channel_id)
            if definition is None:
                raise ValueError(f"unsupported public channel: {channel_id}")
            if definition.availability == "unavailable" and reading.quality != "missing":
                raise ValueError(f"{channel_id} has no supported physical model")
            if reading.value is None:
                continue
            if definition.value_type in {"vector[3]", "vector[4]"}:
                length = 3 if definition.value_type == "vector[3]" else 4
                if not isinstance(reading.value, tuple) or len(reading.value) != length:
                    raise ValueError(f"{channel_id} must be a vector of length {length}")
            elif definition.value_type == "string":
                if not isinstance(reading.value, str):
                    raise ValueError(f"{channel_id} must be a string")
            elif not isinstance(reading.value, (float, int)) or isinstance(reading.value, bool):
                raise ValueError(f"{channel_id} must be a scalar number")
            if isinstance(reading.value, (float, int)) and not math.isfinite(reading.value):
                raise ValueError(f"{channel_id} must be finite")
            bounds = {
                "orbit.latitude_deg": (-90.0, 90.0),
                "orbit.longitude_deg": (-180.0, 180.0),
                "environment.illumination_fraction": (0.0, 1.0),
                "environment.panel_incidence_cosine": (0.0, 1.0),
                "eps.battery_soc": (0.0, 1.0),
                "eps.solar_power_w": (0.0, None),
                "eps.load_requested_w": (0.0, None),
                "eps.load_served_w": (0.0, None),
                "eps.curtailed_power_w": (0.0, None),
                "eps.unserved_power_w": (0.0, None),
                "eps.battery_energy_wh": (0.0, None),
            }.get(channel_id)
            if bounds is not None and isinstance(reading.value, (float, int)):
                lower, upper = bounds
                if reading.value < lower or (upper is not None and reading.value > upper):
                    raise ValueError(f"{channel_id} is outside its public physical range")
            if channel_id == "orbit.longitude_deg" and reading.value == 180.0:
                raise ValueError("orbit.longitude_deg must be less than 180")
        return self


class ModeChangedDetails(PublicModel):
    """Allowlisted observed mode transition details.

    Attributes
    ----------
    from_mode, to_mode : Mode
        Endpoint modes on either side of the public transition.
    """

    from_mode: Mode
    to_mode: Mode


class LowEnergyLimitDetails(PublicModel):
    """Allowlisted observed public SOC limit transition details.

    Attributes
    ----------
    channel_id : str
        Public SOC channel associated with the limit.
    operator : {"lt", "gt"}
        Comparison used to enter or clear the limit.
    value, clear_value : float
        Entry and hysteresis-clear SOC thresholds.
    """

    channel_id: Literal["eps.battery_soc"]
    operator: Literal["lt", "gt"]
    value: Annotated[float, Field(ge=0, le=1)]
    clear_value: Annotated[float, Field(ge=0, le=1)]


class PowerUnservedDetails(PublicModel):
    """Allowlisted observed unserved-power state details.

    Attributes
    ----------
    active : bool
        Whether requested load was not fully served.
    value_w : float
        Unserved requested load in watts.
    sample_window_s : float
        Interval represented by the value in seconds.
    """

    active: bool
    value_w: Annotated[float, Field(ge=0)]
    sample_window_s: Annotated[float, Field(ge=0)]

    @model_validator(mode="after")
    def validate_active_value(self) -> PowerUnservedDetails:
        """Require active state to agree with positive unmet load."""
        if self.active != (self.value_w > 0):
            raise ValueError("active must be true exactly when value_w is positive")
        return self


class OperationSkippedDetails(PublicModel):
    """Allowlisted details of a window the onboard start guard refused.

    Attributes
    ----------
    label : str or None
        Public task identifier of the skipped window.
    mode : Mode
        Mode the window would have commanded.
    start_s, end_s : int
        The skipped half-open window in elapsed simulated seconds.
    battery_soc : float
        Observed state of charge at the start tick.
    min_start_soc : float
        Configured start guard the state of charge was below.
    """

    label: Annotated[str, Field(pattern=ID_PATTERN)] | None
    mode: Mode
    start_s: Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
    end_s: Annotated[int, Field(ge=1, le=MAX_SAFE_INTEGER)]
    battery_soc: Annotated[float, Field(ge=0, le=1)]
    min_start_soc: Annotated[float, Field(ge=0, le=1)]


EventType = Literal[
    "mode_changed",
    "low_energy_limit_entered",
    "low_energy_limit_cleared",
    "power_unserved",
    "operation_skipped",
]
EventDetails = (
    ModeChangedDetails | LowEnergyLimitDetails | PowerUnservedDetails | OperationSkippedDetails
)


class OperationalEvent(PublicModel):
    """Allowlisted observable operational event envelope.

    Attributes
    ----------
    schema_version : str
        Breaking-contract identifier, currently ``operational_event.v1``.
    source_id : str
        Stable producer identity.
    stream_id : UUID
        Stream namespace associated with the event.
    event_sequence : int
        Monotonic sequence within the stream's event namespace.
    satellite_id : str
        Logical spacecraft identity.
    source_kind : {"synthetic", "observed"}
        Provenance of the producer data.
    time_domain : {"simulation_utc", "mission_utc"}
        Meaning of ``observed_at``.
    observed_at, emitted_at : datetime
        UTC event time and producer emission time.
    event_type : EventType
        Allowlisted observable event discriminator.
    reason_code : str
        Stable ASCII reason code for the event.
    details : EventDetails
        Typed details matching ``event_type`` exactly.

    Notes
    -----
    Event details describe an observed condition or transition. Private
    injection schedules and evaluator-only outcome labels are excluded.
    """

    schema_version: Literal["operational_event.v1"]
    source_id: Annotated[str, Field(pattern=ID_PATTERN)]
    stream_id: UUID
    event_sequence: Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
    satellite_id: Annotated[str, Field(pattern=ID_PATTERN)]
    source_kind: Literal["synthetic", "observed"]
    time_domain: Literal["simulation_utc", "mission_utc"]
    observed_at: datetime
    emitted_at: datetime
    event_type: EventType
    reason_code: Annotated[str, Field(min_length=1, max_length=64, pattern=ID_PATTERN)]
    details: EventDetails

    @field_validator("observed_at", "emitted_at")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        """Require RFC 3339 offsets and normalize timestamps to UTC."""
        return _utc_datetime(value)

    @model_validator(mode="after")
    def validate_details_allowlist(self) -> OperationalEvent:
        """Parse only the exact details model permitted for each event type."""
        detail_model = {
            "mode_changed": ModeChangedDetails,
            "low_energy_limit_entered": LowEnergyLimitDetails,
            "low_energy_limit_cleared": LowEnergyLimitDetails,
            "power_unserved": PowerUnservedDetails,
            "operation_skipped": OperationSkippedDetails,
        }[self.event_type]
        if not isinstance(self.details, detail_model):
            raise ValueError(f"{self.event_type} requires {detail_model.__name__}")
        return self


__all__ = ["ChannelReading", "MeasurementFrame", "OperationalEvent"]
