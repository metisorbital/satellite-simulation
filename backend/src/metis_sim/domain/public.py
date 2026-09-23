"""Allowlisted public API projections, independent of persistence records."""

from datetime import datetime
from typing import Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, with_config

from metis_sim.domain.telemetry import MeasurementFrame

RunState = Literal["created", "running", "paused", "completed", "stopped", "failed", "aborted"]
Action = Literal["start", "pause", "resume", "stop", "set_speed"]


class PublicModel(BaseModel):
    """Base for strict, immutable public response projections.

    Notes
    -----
    Extra fields and non-finite numbers are rejected so private model state
    cannot cross the response boundary accidentally.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class PublicLimit(PublicModel):
    """A disclosed operational limit with hysteresis.

    Attributes
    ----------
    channel_id : str
        Public channel monitored by this limit.
    operator : {"lt", "gt"}
        Comparison used to enter the limit.
    value, clear_value : float
        Entry and clear thresholds exposed to a viewer or consumer.
    """

    channel_id: Literal["eps.battery_soc"]
    operator: Literal["lt", "gt"]
    value: float
    clear_value: float


class PublicSpacecraft(PublicModel):
    """Public nameplate and display properties of one spacecraft.

    Attributes
    ----------
    satellite_id : str
        Stable spacecraft identity.
    name, color : str
        Human-readable label and viewer marker color.
    stream_id : str
        Durable public telemetry stream identity.
    capacity_wh, panel_area_m2 : float
        Disclosed battery capacity and panel area.
    public_limits : list of PublicLimit
        Configured limits safe to disclose to consumers.
    """

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
    """Committed run status containing no configuration or scenario identity.

    Attributes
    ----------
    run_id : str
        Identifier for this execution.
    status : RunState
        Public lifecycle state.
    epoch_utc : datetime
        Run start epoch in UTC.
    duration_s : int
        Configured simulated duration.
    committed_tick : int
        Latest durably committed simulated second, or ``-1`` before the
        first commit.
    status_revision : int
        Monotonic status revision used to order same-tick responses.
    committed_at : datetime or None
        Simulation UTC timestamp of the latest committed sample; ``None``
        before the first sample.
    requested_speed, effective_speed : float or int
        Requested pacing multiplier and measured effective multiplier.
    wall_lag_s : float
        Difference between requested simulated progress and wall pacing.
    satellites : list of PublicSpacecraft
        Public spacecraft descriptors and stream identities.
    source_kind : str
        Provenance label; P0 runs are ``synthetic``.
    model_provenance : PublicModelProvenance
        Allowlisted model and Earth-orientation metadata.
    frame_count : int
        Number of committed public frames.
    diagnostic : str or None
        Safe terminal or health diagnostic, when present.

    Notes
    -----
    Seeds, scenario parameters, private manifests, and future outcome labels
    are intentionally excluded from this projection.
    """

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
    """A consistent committed status and bounded measurement history.

    Attributes
    ----------
    status : PublicRunStatus
        Status and committed endpoint corresponding to the history.
    frames : list of MeasurementFrame
        Public frames in the bounded history window, all at or before the
        committed endpoint.
    """

    status: PublicRunStatus
    frames: list[MeasurementFrame]


class OrbitPoint(PublicModel):
    """One authoritative Earth-fixed orbit state without predicted health.

    Attributes
    ----------
    elapsed_s : int
        Simulated elapsed time from the run epoch.
    observed_at : datetime
        UTC timestamp represented by the state.
    position_itrs_m : tuple of float
        Earth-fixed position in metres.
    velocity_itrs_m_s : tuple of float
        Earth-fixed velocity in metres per second.
    """

    elapsed_s: int
    observed_at: datetime
    position_itrs_m: tuple[float, float, float]
    velocity_itrs_m_s: tuple[float, float, float]


class SatelliteTrajectory(PublicModel):
    """Orbit samples for one spacecraft.

    Attributes
    ----------
    satellite_id : str
        Spacecraft identity.
    samples : list of OrbitPoint
        Ordered Earth-fixed orbit samples.
    """

    satellite_id: str
    samples: list[OrbitPoint]


class Trajectory(PublicModel):
    """Bounded orbit-only prediction with explicit coordinates.

    Attributes
    ----------
    run_id : str
        Run whose prepared engine produced the samples.
    kind : str
        Explicit ``predicted_orbit`` discriminator.
    frame : str
        Coordinate frame, fixed to ``ITRS`` in P0.
    satellites : list of SatelliteTrajectory
        Per-spacecraft orbit samples.

    Notes
    -----
    This projection contains no future electrical or health state.
    """

    run_id: str
    kind: Literal["predicted_orbit"] = "predicted_orbit"
    frame: Literal["ITRS"] = "ITRS"
    satellites: list[SatelliteTrajectory]


class SequenceRange(PublicModel):
    """A delivered stream's inclusive sequence bounds.

    Attributes
    ----------
    stream_id : str
        Public stream identity.
    first, last : int
        Inclusive sequence numbers represented by a delivery batch.
    """

    stream_id: str
    first: int
    last: int


class VisualMessage(PublicModel):
    """Bounded public presentation transport; never a durable consumer offset.

    Attributes
    ----------
    visual_schema_version : str
        Version of the presentation message envelope.
    type : str
        Presentation message kind, such as ``snapshot`` or ``samples``.
    sent_at : datetime
        Wall-clock send time in UTC.
    run_id : str
        Run associated with the presentation update.
    status : PublicRunStatus or None
        Latest public status when supplied.
    frames : list of MeasurementFrame
        Coalesced public frames delivered to the viewer.
    ranges : list of SequenceRange
        Inclusive sequence bounds for delivered streams.
    message : str or None
        Safe human-readable error or resynchronization message.

    Notes
    -----
    Consumers requiring durable delivery must use the HTTP replay routes and
    their opaque cursors.
    """

    visual_schema_version: Literal["visual.v1"] = "visual.v1"
    type: Literal["snapshot", "samples", "clock", "lifecycle", "resync_required", "error"]
    sent_at: datetime
    run_id: str
    status: PublicRunStatus | None = None
    frames: list[MeasurementFrame] = Field(default_factory=list)
    ranges: list[SequenceRange] = Field(default_factory=list)
    message: str | None = None


class ViewerBootstrap(PublicModel):
    """One prepared run and session-bound CSRF token for the browser.

    Attributes
    ----------
    csrf_token : str
        Token required on browser control requests for this session.
    run : PublicRunStatus
        Public status of the session's one scoped run.
    """

    csrf_token: str
    run: PublicRunStatus


class ControlRequest(PublicModel):
    """A run command; speed is meaningful only for ``set_speed``.

    Attributes
    ----------
    action : Action
        Lifecycle command to apply to the run.
    speed : {1, 5, 20} or None
        Requested pacing multiplier for ``set_speed``; omitted otherwise.
    """

    action: Action
    speed: Literal[1, 5, 20] | None = None
