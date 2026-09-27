"""Illustrative mission execution, separate from the recorded measurement stream."""

from collections.abc import Mapping
from typing import Any

import numpy as np

from metis_agent.models import MetisAlert, MinuteSeries, MissionLaneOutcome, RunOutcome, TaskState


def _projected_outcome(state: Mapping[str, Any], status: Mapping[str, Any]) -> RunOutcome:
    """Advance the demo scenario using its saved plan margin and replay clock.

    Parameters
    ----------
    state : mapping
        Durable mission assumptions, forecast, approved plan and operator case.
    status : mapping
        Public recorded status. Source ticks are elapsed seconds, not row indices.

    Returns
    -------
    RunOutcome
        Explicit demo projection. Downlink admission requires a nonnegative
        saved budget margin throughout its complete window. Other task failures
        use the first budget crossing. Recorded measurements remain unchanged.
    """
    minute = max(0.0, (int(status["committed_tick"]) - state["mission_start_s"]) / 60)
    minute = min(minute, float(state["mission"]["duration_min"]))
    curve = state["proposal"]["proposed_margin" if state["plan"] == "metis" else "original_margin"]
    times, values = np.asarray(curve["minute"], float), np.asarray(curve["value"], float)
    pairs = [(float(t), float(v)) for t, v in zip(times, values, strict=True) if t <= minute]
    low = min(pairs, key=lambda point: point[1]) if pairs else None
    windows = {task["task_id"]: task for task in state["tasks"]}

    def failure(start: float, end: float) -> float | None:
        points = np.concatenate(([start], times[(times > start) & (times < end)], [end]))
        margins = np.interp(points, times, values)
        negative = np.flatnonzero(margins < 0)
        if not negative.size:
            return None
        index = int(negative[0])
        if index == 0:
            return start
        a, b = float(points[index - 1]), float(points[index])
        before, after = float(margins[index - 1]), float(margins[index])
        return a + (b - a) * before / (before - after)

    failures = {
        key: failure(task["start_s"] / 60, task["end_s"] / 60) for key, task in windows.items()
    }

    def task_state(task_id: str) -> TaskState:
        task = windows[task_id]
        if minute * 60 < task["start_s"]:
            return "pending"
        failed = failures[task_id]
        if task_id == "downlink" and failed is not None:
            return "skipped"
        if failed is not None and minute >= failed:
            return "skipped"
        return "running" if minute * 60 < task["end_s"] else "done"

    capture, batch, downlink = (
        task_state(key) for key in ("thermal_capture", "compute_batch", "downlink")
    )
    if capture == "skipped" and minute * 60 >= windows["downlink"]["start_s"]:
        downlink = "skipped"
    radio = windows["downlink"]
    radio_start, radio_end = radio["start_s"] / 60, radio["end_s"] / 60
    radio_until = min(
        minute, failures["downlink"] if failures["downlink"] is not None else radio_end
    )
    progress = max(0.0, min(1.0, (radio_until - radio_start) / (radio_end - radio_start)))
    if capture == "skipped" or failures["downlink"] is not None:
        progress = 0.0
    delivered = (
        capture == "done"
        and downlink == "done"
        and radio_end <= state["mission"]["delivery_deadline_min"]
    )
    negative = failure(0, minute) if minute else None
    alert = (
        MetisAlert.model_validate(state["alert"])
        if state.get("enabled", True) and state.get("case_id")
        else None
    )

    def margin_at(tick: int) -> float | None:
        return round(float(np.interp(tick / 60, times, values)), 6) if minute * 60 >= tick else None

    return RunOutcome(
        run_id=state["run_id"],
        plan=state["plan"],
        name=state["satellite_id"],
        metis_on=state.get("enabled", True),
        alert=alert,
        committed_min=round(minute, 3),
        complete=minute >= radio_end,
        threshold_wh=None,
        limit_soc=None,
        batch_start_min=windows["compute_batch"]["start_s"] / 60,
        margin=MinuteSeries(minute=[t for t, _ in pairs], value=[v for _, v in pairs]),
        solar_w=MinuteSeries(minute=[], value=[]),
        min_wh=low[1] if low else None,
        min_at_min=low[0] if low else None,
        first_negative_min=round(negative, 6) if negative is not None else None,
        capture_end_wh=margin_at(windows["thermal_capture"]["end_s"]),
        downlink_start_wh=margin_at(radio["start_s"]),
        downlink_end_wh=margin_at(radio["end_s"]),
        downlink_start_soc=None,
        capture=capture,
        batch=batch,
        downlink=downlink,
        downlink_progress=round(progress, 6),
        delivered_at_min=radio_end if delivered else None,
        source_kind="observed",
        outcome_basis="demo_projection",
        satellite_id=state["satellite_id"],
        case_id=state.get("case_id"),
    )


def recorded_outcome(state: Mapping[str, Any], status: Mapping[str, Any]) -> RunOutcome:
    """Return the active demo and two explicitly identified comparison lanes.

    Parameters
    ----------
    state : mapping
        Durable mission, enabled preference and audited approved-plan snapshot.
    status : mapping
        Public source-clock status shared by both comparison lanes.

    Returns
    -------
    RunOutcome
        The original baseline always advances with source time. The saved Metis
        proposal advances only after the exact proposal is approved; otherwise
        its task states remain pending and its downlink progress stays zero.
    """
    original_tasks = [
        {
            "task_id": task["task_id"],
            "start_s": round(task["start_min"] * 60),
            "end_s": round(task["end_min"] * 60),
            "added_load_w": task["added_load_w"],
        }
        for task in state["mission"]["tasks"]
    ]
    original = _projected_outcome({**state, "plan": "original", "tasks": original_tasks}, status)
    approval = state.get("approved_plan")
    enabled = bool(state.get("enabled", True))
    approved = (
        enabled
        and state["plan"] == "metis"
        and approval is not None
        and approval.get("proposal_id") == state["proposal_id"]
        and state.get("case_id") is not None
        and state["alert"]["state"] == "approved"
    )
    original_lane = MissionLaneOutcome(
        plan="original",
        capture=original.capture,
        batch=original.batch,
        downlink=original.downlink,
        downlink_progress=original.downlink_progress,
        delivered_at_min=original.delivered_at_min,
        batch_start_min=original.batch_start_min,
        execution_status="comparison" if approved else "active",
        label="Original schedule · comparison" if approved else "Original schedule · active demo",
        provenance="comparison_demo_projection" if approved else "active_demo_projection",
    )
    if approved:
        assert approval is not None
        active = _projected_outcome({**state, "tasks": approval["tasks"]}, status)
        proposed_lane = MissionLaneOutcome(
            plan="metis",
            capture=active.capture,
            batch=active.batch,
            downlink=active.downlink,
            downlink_progress=active.downlink_progress,
            delivered_at_min=active.delivered_at_min,
            batch_start_min=active.batch_start_min,
            execution_status="active",
            label="Approved Metis plan · active demo",
            provenance="active_demo_projection",
        )
    else:
        active = original
        waiting = enabled and state["status"] in {"watching", "awaiting_decision"}
        proposed_lane = MissionLaneOutcome(
            plan="metis",
            capture="pending",
            batch="pending",
            downlink="pending",
            downlink_progress=0,
            delivered_at_min=None,
            batch_start_min=float(state["proposal"]["to_start_min"]),
            execution_status="awaiting_approval" if waiting else "inactive",
            label=(
                "Metis off · enable before a new run"
                if not enabled
                else "Metis proposal · awaiting operator approval"
                if waiting
                else "Metis proposal · not applied"
            ),
            provenance="inactive_proposal",
        )
    return active.model_copy(update={"comparison": [original_lane, proposed_lane]})
