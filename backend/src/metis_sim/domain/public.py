"""Allowlisted public API projections, independent of persistence records."""

from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, with_config

from metis_sim.domain.telemetry import MeasurementFrame

RunState = Literal["created", "running", "paused", "completed", "stopped", "failed", "aborted"]
Action = Literal["start", "pause", "resume", "stop", "set_speed"]


class PublicModel(BaseModel):
    """Reject accidental fields at the public projection boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class PublicLimit(PublicModel):
    """A disclosed operational limit with hysteresis."""

    channel_id: Literal["eps.battery_soc"]
    operator: Literal["lt", "gt"]
    value: float
    clear_value: float


class PublicSpacecraft(PublicModel):
    """Public nameplate and display properties of one spacecraft."""

    satellite_id: str
    name: str
    color: str
    stream_id: str
    capacity_wh: float
    panel_area_m2: float
    public_limits: list[PublicLimit] = Field(default_factory=list)


@with_config(ConfigDict(extra="forbid", strict=True, allow_inf_nan=False))
class PublicModelProvenance(TypedDict, total=False):
    """Allowlisted public model and Earth-orientation provenance.

    Notes
    -----
    Fields may be absent when the producer has not supplied that metadata.
    Unknown fields are rejected so private manifest parameters cannot cross
    the public response boundary through an unrestricted metadata mapping.
    """

    frame: str
    inertial_frame: str
    earth_orientation_source: str
    iers_sha256: str
    leap_seconds_sha256: str
    iers_first_mjd: float
    iers_last_mjd: float
    iers_values: Literal["observed", "predicted"]
    leap_seconds_expiry: str
    coverage_validated: bool
    network_updates: bool
    time_advance_scale: str
    astropy_version: str
    astropy_iers_data_version: str
    erfa_version: str
    numpy_version: str
    earth_model: str
    orbit_model: str
    integrator: str
    midpoint_model: str
    sun_model: str
    eclipse_model: str
    panel_model: str
    force_model_limits: str
    eps_model_limits: str
    accuracy_claim: str


class PublicRunStatus(PublicModel):
    """Committed run status containing no configuration or scenario identity."""

    run_id: str
    status: RunState
    epoch_utc: datetime
    duration_s: int
    committed_tick: int = -1
    status_revision: int = 0
    committed_at: datetime | None = None
    requested_speed: Literal[1, 5, 20]
    effective_speed: float = 0
    wall_lag_s: float = 0
    satellites: list[PublicSpacecraft]
    source_kind: Literal["synthetic"] = "synthetic"
    model_provenance: PublicModelProvenance
    frame_count: int = 0
    diagnostic: str | None = None


class Snapshot(PublicModel):
    """A consistent committed status and bounded measurement history."""

    status: PublicRunStatus
    frames: list[MeasurementFrame]


class OrbitPoint(PublicModel):
    """One authoritative Earth-fixed orbit state without predicted health."""

    elapsed_s: int
    observed_at: datetime
    position_itrs_m: tuple[float, float, float]
    velocity_itrs_m_s: tuple[float, float, float]


class SatelliteTrajectory(PublicModel):
    """Orbit samples for one spacecraft."""

    satellite_id: str
    samples: list[OrbitPoint]


class Trajectory(PublicModel):
    """Bounded orbit-only prediction with explicit coordinates."""

    run_id: str
    kind: Literal["predicted_orbit"] = "predicted_orbit"
    frame: Literal["ITRS"] = "ITRS"
    satellites: list[SatelliteTrajectory]


class SequenceRange(PublicModel):
    """A delivered stream's inclusive sequence bounds."""

    stream_id: str
    first: int
    last: int


class VisualMessage(PublicModel):
    """Bounded public presentation transport; never a durable consumer offset."""

    visual_schema_version: Literal["visual.v1"] = "visual.v1"
    type: Literal["snapshot", "samples", "clock", "lifecycle", "resync_required", "error"]
    sent_at: datetime
    run_id: str
    status: PublicRunStatus | None = None
    frames: list[MeasurementFrame] = Field(default_factory=list)
    ranges: list[SequenceRange] = Field(default_factory=list)
    message: str | None = None


class ViewerBootstrap(PublicModel):
    """One prepared run and session-bound CSRF token for the browser."""

    csrf_token: str
    run: PublicRunStatus


class ControlRequest(PublicModel):
    """A run command; speed is meaningful only for set_speed."""

    action: Action
    speed: Literal[1, 5, 20] | None = None
