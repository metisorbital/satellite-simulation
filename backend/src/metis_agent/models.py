"""Public Metis demo contracts; Dart types are generated from these models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MetisModel(BaseModel):
    """Frozen contract base that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class MinuteSeries(MetisModel):
    """Values at mission minutes.

    Attributes
    ----------
    minute : list of float
        Mission minutes from T0.
    value : list of float
        One value per minute entry.
    """

    minute: list[float]
    value: list[float]


class MissionTask(MetisModel):
    """One scheduled task of the original plan.

    Attributes
    ----------
    task_id : str
        ``compute_batch``, ``thermal_capture`` or ``downlink``.
    name : str
        Display name.
    start_min, end_min : float
        Mission minutes from T0.
    added_load_w : float
        Load added to the essential load while active.
    movable : bool
        Whether Metis may move this task.
    """

    task_id: str
    name: str
    start_min: float
    end_min: float
    added_load_w: float
    movable: bool


class MissionInterval(MetisModel):
    """A mission-minute interval, such as an eclipse.

    Attributes
    ----------
    start_min, end_min : float
        Mission minutes from T0.
    """

    start_min: float
    end_min: float


class MissionBrief(MetisModel):
    """The emergency request and the assumed mission.

    Attributes
    ----------
    title : str
        Mission name.
    request : str
        What the response team asked for.
    t0_utc : str
        Planning-uplink closure (mission minute 0) in UTC.
    decision_min : float
        Mission minute when the request arrived, negative before T0.
    duration_min : float
        Mission length after T0.
    tasks : list of MissionTask
        Original schedule.
    eclipses : list of MissionInterval
        Assumed eclipse windows.
    delivery_deadline_min, batch_deadline_min : float
        Briefing and batch deadlines.
    reserve_wh : float
        Usable margin above the protected reserve at T0.
    environment_source : str or None
        Public name of the recorded data behind the simulated conditions,
        supplied by the host.
    """

    title: str
    request: str
    t0_utc: str
    decision_min: float
    duration_min: float
    tasks: list[MissionTask]
    eclipses: list[MissionInterval]
    delivery_deadline_min: float
    batch_deadline_min: float
    reserve_wh: float
    environment_source: str | None


class ForecastBand(MetisModel):
    """Per-5-minute forecast in mission watts.

    Attributes
    ----------
    p10, p50, p90 : list of float
        Low case, median and high case.
    cautious : list of float
        The inputs Metis plans with.
    nominal : list of float
        Fixed assumption for comparison.
    """

    p10: list[float]
    p50: list[float]
    p90: list[float]
    cautious: list[float]
    nominal: list[float]


class MetisForecast(MetisModel):
    """Forecast made at the decision time.

    Attributes
    ----------
    source : str
        Training data and model description.
    decision_time_source : str
        Decision time in the source dataset's clock.
    trained_through : str
        Last day of training data.
    caution_lambda : float
        Calibrated caution setting.
    bin_minutes : float
        Bin width.
    bin_start_min : list of float
        Bin starts in mission minutes.
    solar_w, essential_w : ForecastBand
        Solar supply and essential load.
    """

    source: str
    decision_time_source: str
    trained_through: str
    caution_lambda: float
    bin_minutes: float
    bin_start_min: list[float]
    solar_w: ForecastBand
    essential_w: ForecastBand


class Alternative(MetisModel):
    """Slot another planner input would choose.

    Attributes
    ----------
    planner : str
        Input name.
    start_min : float or None
        Chosen batch start.
    status : str
        Planner status.
    """

    planner: str
    start_min: float | None
    status: str


class MetisProposal(MetisModel):
    """The proposed schedule change.

    Attributes
    ----------
    proposal_id : str
        Stable identity of this proposal.
    task_id : str
        Task being moved.
    from_start_min, to_start_min : float
        Original and proposed start.
    status : str
        Planner status for the proposal.
    rationale : str
        Plain-language reason.
    original_crossing_min : float or None
        Where the original plan enters the reserve under the cautious forecast.
    original_downlink_start_wh, proposed_downlink_start_wh : float
        Margin when the downlink starts.
    proposed_min_wh : float
        Lowest margin of the proposed plan under the cautious forecast.
    original_margin, proposed_margin : MinuteSeries
        Forecast margins, one point per minute.
    alternatives : list of Alternative
        Slots chosen from other inputs.
    """

    proposal_id: str
    task_id: str
    from_start_min: float
    to_start_min: float
    status: str
    rationale: str
    original_crossing_min: float | None
    original_downlink_start_wh: float
    proposed_downlink_start_wh: float
    proposed_min_wh: float
    original_margin: MinuteSeries
    proposed_margin: MinuteSeries
    alternatives: list[Alternative]


class ApprovalWindow(MetisModel):
    """The operator's approval window before T0.

    Attributes
    ----------
    state : {"open", "approved", "closed"}
        Current window state.
    opened_at, closes_at : str
        UTC wall-clock bounds.
    remaining_s : float
        Seconds left while open.
    approved_by, approved_at : str or None
        Approval record.
    """

    state: Literal["open", "approved", "closed"]
    opened_at: str
    closes_at: str
    remaining_s: float
    approved_by: str | None
    approved_at: str | None


class PlanRuns(MetisModel):
    """The operator's latest demo run with Metis off and with Metis on.

    Attributes
    ----------
    metis_off, metis_on : str or None
        Run IDs, or ``None`` when that mode has not flown since the last reset.
        With Metis on this is the watched run, or the Metis-plan run that
        continued it after approval.
    """

    metis_off: str | None
    metis_on: str | None


class DemoResult(MetisModel):
    """Persisted illustrative delivery result, separate from observed telemetry.

    Attributes
    ----------
    result : str
        Delivery success, delivery failure, or failed illustrative capture.
    plan : str
        Original or operator-approved schedule used by the budget projection.
    recorded_at_utc : str
        Source-clock timestamp when the modeled downlink window ended.
    capture, downlink : str
        Projected terminal task states, not measured spacecraft execution.
    delivered_at_min : float or None
        Illustrative delivery time; absent when the scenario could not deliver.
    outcome_basis : str
        Explicit demo-projection provenance.
    """

    result: Literal["delivered", "missed_delivery", "capture_failed"]
    plan: Literal["original", "metis"]
    recorded_at_utc: str
    capture: Literal["pending", "running", "done", "skipped"]
    downlink: Literal["pending", "running", "done", "skipped"]
    delivered_at_min: float | None
    outcome_basis: Literal["demo_projection"] = "demo_projection"


class MissionState(MetisModel):
    """Public summary of one durable recorded mission.

    Attributes
    ----------
    run_id, satellite_id : str
        Existing replay and real spacecraft identities.
    status : str
        Durable planning and review state, never a measured task outcome.
    plan : str
        Original or operator-approved saved schedule.
    case_id : str or None
        Standard operator investigation for this prediction.
    mission_epoch_utc : str
        Mission origin aligned to the recorded source timestamp.
    enabled : bool, default=True
        Whether this replay can raise the saved prediction alert and hold.
    """

    run_id: str
    satellite_id: str
    status: Literal[
        "watching", "awaiting_decision", "approved", "dismissed", "reviewed", "interrupted"
    ]
    plan: Literal["original", "metis"]
    case_id: str | None
    mission_epoch_utc: str
    enabled: bool = True
    demo_result: DemoResult | None = None


class MetisPreferenceRequest(MetisModel):
    """Set model watching for the current compatible recorded mission.

    Attributes
    ----------
    enabled : bool
        Whether the saved prediction can pause replay for an operator case.
    """

    enabled: bool


class MetisBriefing(MetisModel):
    """Everything the Metis view shows before a run.

    Attributes
    ----------
    mission : MissionBrief
        Request and original schedule.
    forecast : MetisForecast
        Forecast made at the decision time.
    proposal : MetisProposal
        Proposed change.
    window : ApprovalWindow
        Approval state.
    runs : PlanRuns
        Latest run of each mode, for resuming and comparing.
    """

    mission: MissionBrief
    forecast: MetisForecast
    proposal: MetisProposal
    window: ApprovalWindow
    runs: PlanRuns
    mission_state: MissionState | None = None
    mission_available: bool = True
    unavailable_reason: str | None = None
    metis_enabled: bool = True
    alert_at_utc: str | None = None
    alert_at_min: float | None = None


class TaskWindow(MetisModel):
    """One task in simulator seconds from T0.

    Attributes
    ----------
    task_id : str
        Task label.
    start_s, end_s : int
        Half-open window.
    added_load_w : float
        Load added while active.
    """

    task_id: str
    start_s: int
    end_s: int
    added_load_w: float


Plan = Literal["original", "metis"]
"""``original`` flies the schedule as planned; ``metis`` flies the approved proposal."""

TaskState = Literal["pending", "running", "done", "skipped"]
"""Task progress from public telemetry; ``skipped`` means the onboard start guard refused it."""


class ApprovedPlan(MetisModel):
    """An approved proposal and the task windows the Metis plan flies.

    Attributes
    ----------
    proposal_id : str
        Approved proposal.
    approved_by : str
        Operator display name.
    approved_at : str
        UTC wall-clock time.
    tasks : list of TaskWindow
        The original schedule with the proposed change applied.
    """

    proposal_id: str
    approved_by: str
    approved_at: str
    tasks: list[TaskWindow]


class MetisAlert(MetisModel):
    """Metis's alert on a run it watches, and the operator's decision.

    Attributes
    ----------
    state : {"pending", "approved", "dismissed"}
        ``pending`` holds the run until the operator decides.
    raised_at_min : float
        Mission minute the alert was raised, before the batch starts.
    decided_by : str or None
        Operator who approved or dismissed it.
    """

    state: Literal["pending", "approved", "dismissed"]
    raised_at_min: float
    decided_by: str | None


class MissionLaneOutcome(MetisModel):
    """One backend-authored scenario lane on the shared recorded clock.

    Attributes
    ----------
    plan : str
        Original schedule or saved Metis proposal.
    capture, batch, downlink : str
        Modeled task states. Inactive proposals remain pending.
    downlink_progress : float
        Modeled transmission fraction, zero when admission is refused.
    delivered_at_min : float or None
        Illustrative delivery minute, never a measured image receipt.
    batch_start_min : float
        Original or proposed compute-batch start.
    execution_status : str
        Active demo, counterfactual comparison, waiting approval or inactive.
    label : str
        User-facing execution status authored by the backend.
    provenance : str
        Explicit separation of active demo projection and comparison proposal.
    """

    plan: Plan
    capture: TaskState
    batch: TaskState
    downlink: TaskState
    downlink_progress: float
    delivered_at_min: float | None
    batch_start_min: float
    execution_status: Literal["active", "comparison", "awaiting_approval", "inactive"]
    label: str
    provenance: Literal["active_demo_projection", "comparison_demo_projection", "inactive_proposal"]


class RunOutcome(MetisModel):
    """Modeled mission progression and comparison, paced by public replay time.

    Attributes
    ----------
    run_id : str
        Demo run.
    plan : {"original", "metis"}
        Plan the run flies.
    name : str
        Plan display name.
    metis_on : bool
        Whether Metis watched the mission.
    alert : MetisAlert or None
        Metis's alert and decision, for runs flown with Metis on.
    committed_min : float
        Mission minute committed so far.
    complete : bool
        Whether the run reached its end.
    threshold_wh : float
        Battery energy at the top of the protected reserve.
    limit_soc : float
        State of charge at the top of the reserve: the public low-energy limit.
    batch_start_min : float
        Compute-batch start of this plan.
    margin : MinuteSeries
        Saved requested-budget margin; separate from observed battery readings.
    solar_w : MinuteSeries
        Measured harvested solar, one-minute means.
    min_wh, min_at_min : float or None
        Lowest margin so far and when.
    first_negative_min : float or None
        First time inside the reserve.
    capture_end_wh, downlink_start_wh, downlink_end_wh : float or None
        Margins at the task edges once reached.
    downlink_start_soc : float or None
        Battery state of charge when the downlink was due.
    capture, batch, downlink : {"pending", "running", "done", "skipped"}
        Task progress.
    downlink_progress : float
        Fraction of the downlink window completed, 0 to 1.
    delivered_at_min : float or None
        Illustrative image delivery when an admitted modeled downlink completes.
    comparison : list of MissionLaneOutcome
        Original baseline and approval-gated Metis lane on the same source clock.
    """

    run_id: str
    plan: Plan
    name: str
    metis_on: bool
    alert: MetisAlert | None
    committed_min: float
    complete: bool
    threshold_wh: float | None
    limit_soc: float | None
    batch_start_min: float
    margin: MinuteSeries
    solar_w: MinuteSeries
    min_wh: float | None
    min_at_min: float | None
    first_negative_min: float | None
    capture_end_wh: float | None
    downlink_start_wh: float | None
    downlink_end_wh: float | None
    downlink_start_soc: float | None
    capture: TaskState
    batch: TaskState
    downlink: TaskState
    downlink_progress: float
    delivered_at_min: float | None
    source_kind: Literal["observed", "synthetic"] = "synthetic"
    outcome_basis: str = "public_telemetry"
    satellite_id: str | None = None
    case_id: str | None = None
    comparison: list[MissionLaneOutcome] = Field(default_factory=list)


class ViewerMissionRunRequest(MetisModel):
    """Fly one plan of the wildfire mission.

    Attributes
    ----------
    plan : {"original", "metis"}
        Plan to fly. ``metis`` requires an approved proposal and continues the
        watched run from the alert.
    proposal_id : str or None
        Approved proposal, required for ``metis``.
    watch : bool, default=False
        Fly the original plan with Metis on: the run starts at T0, pauses by
        itself at Metis's alert and waits for the operator's decision.
    """

    plan: Plan
    proposal_id: str | None = None
    watch: bool = False


_MODELS: tuple[type[BaseModel], ...] = (
    MinuteSeries,
    MissionTask,
    MissionInterval,
    MissionBrief,
    ForecastBand,
    MetisForecast,
    Alternative,
    MetisProposal,
    ApprovalWindow,
    PlanRuns,
    DemoResult,
    MissionState,
    MetisPreferenceRequest,
    MetisBriefing,
    MetisAlert,
    TaskWindow,
    ApprovedPlan,
    MissionLaneOutcome,
    RunOutcome,
    ViewerMissionRunRequest,
)
METIS_MODELS: dict[str, tuple[type[BaseModel], Literal["validation", "serialization"]]] = {
    model.__name__: (
        model,
        "validation"
        if model in {ViewerMissionRunRequest, MetisPreferenceRequest}
        else "serialization",
    )
    for model in _MODELS
}
