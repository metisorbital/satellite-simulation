"""Forecast, proposal and plan task windows from the packaged decision artifact."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from typing import Any

import numpy as np

from metis_agent import planner
from metis_agent.models import (
    Alternative,
    ForecastBand,
    MetisForecast,
    MetisProposal,
    MinuteSeries,
    MissionBrief,
    MissionInterval,
    MissionTask,
    Plan,
    TaskWindow,
)

ARTIFACT = "data/decision-bupt1-20230621T1250.json"
PLAN_NAMES: dict[Plan, str] = {"original": "Original schedule", "metis": "Metis plan"}
ALTERNATIVES = (
    ("nominal", "Nominal budget"),
    ("orbit_repeat", "Repeat last orbit"),
    ("median", "Metis median forecast"),
)


@dataclass(frozen=True)
class Decision:
    """The decision Metis prepared at the request time.

    Attributes
    ----------
    mission : MissionBrief
        Request and original schedule.
    forecast : MetisForecast
        Forecast bands in mission watts.
    proposal : MetisProposal
        Proposed batch move with forecast margins.
    """

    mission: MissionBrief
    forecast: MetisForecast
    proposal: MetisProposal

    def plan_tasks(self, plan: Plan) -> list[TaskWindow]:
        """Return the task windows a plan flies, in simulator seconds from T0.

        Parameters
        ----------
        plan : {"original", "metis"}
            ``original`` keeps the batch at its original start; ``metis``
            moves it to the proposed start.

        Returns
        -------
        list of TaskWindow
            Batch, capture and downlink windows.
        """
        tasks = []
        for task in self.mission.tasks:
            start = task.start_min
            if task.movable and plan == "metis":
                start = self.proposal.to_start_min
            length = task.end_min - task.start_min
            tasks.append(
                TaskWindow(
                    task_id=task.task_id,
                    start_s=round(start * 60),
                    end_s=round((start + length) * 60),
                    added_load_w=task.added_load_w,
                )
            )
        return tasks


def _load_artifact() -> tuple[dict[str, Any], bytes]:
    raw = resources.files("metis_agent").joinpath(ARTIFACT).read_bytes()
    return json.loads(raw), raw


def _sunlit(mission: planner.Mission, bin_start: list[float]) -> np.ndarray:
    mid = np.asarray(bin_start) + mission["binMinutes"] / 2
    dark = np.zeros(mid.size, bool)
    for a, b in mission["eclipses"]:
        dark |= (mid >= a) & (mid < b)
    return ~dark


def _series(margins: np.ndarray, mission: planner.Mission) -> MinuteSeries:
    stride = round(1 / mission["step"])
    minutes = np.arange(0, margins.size, stride) * mission["step"]
    return MinuteSeries(
        minute=[round(float(m), 4) for m in minutes],
        value=[round(float(v), 6) for v in margins[::stride]],
    )


def build_decision(t0_utc: str, environment_source: str | None = None) -> Decision:
    """Build the decision from the artifact and the planner.

    Parameters
    ----------
    t0_utc : str
        Mission minute 0 in UTC, from the host's demo template.
    environment_source : str or None
        Public name of the recorded data behind the host's simulated conditions.

    Returns
    -------
    Decision
        Mission, forecast and proposal. The proposal is recomputed by the
        planner and must equal the artifact's recorded choice.
    """
    artifact, raw = _load_artifact()
    mission = planner.load_mission()
    mapping, bins = artifact["mapping"], artifact["bin_start_min"]
    sunlit = _sunlit(mission, bins)
    reference = np.maximum(np.asarray(mapping["reference"], float), mapping["floorW"])

    def solar(values: list[float]) -> list[float]:
        mission_w = mission["solarW"] * np.clip(np.asarray(values) / reference, 0, mapping["cap"])
        return [round(float(v), 6) for v in np.where(sunlit, mission_w, 0.0)]

    def essential(values: list[float]) -> list[float]:
        return [
            round(float(v), 6)
            for v in mission["essentialW"] * np.asarray(values) / mapping["hNominalW"]
        ]

    cautious = artifact["mission_inputs"]["cautious"]
    raw_solar, raw_house = artifact["raw"]["solar_w"], artifact["raw"]["housekeeping_w"]
    forecast = MetisForecast(
        source=(
            f"Gradient-boosted quantile models trained on {artifact['source']['dataset']} "
            f"telemetry ({artifact['source']['training_origins']:,} forecast origins), "
            "retrained weekly; each model corrects repeating the last orbit."
        ),
        decision_time_source=f"{artifact['source']['decision_time']} (BUPT-1 time)",
        trained_through=artifact["source"]["last_training_origin"][:10],
        caution_lambda=artifact["source"]["lambda"],
        bin_minutes=artifact["bin_minutes"],
        bin_start_min=[float(b) for b in bins],
        solar_w=ForecastBand(
            p10=solar(raw_solar["p10"]),
            p50=solar(raw_solar["center"]),
            p90=solar(raw_solar["p90"]),
            cautious=[round(float(v), 6) for v in np.where(sunlit, cautious["solar_w"], 0.0)],
            nominal=[float(mission["solarW"]) if s else 0.0 for s in sunlit],
        ),
        essential_w=ForecastBand(
            p10=essential(raw_house["p10"]),
            p50=essential(raw_house["center"]),
            p90=essential(raw_house["p90"]),
            cautious=[round(float(v), 6) for v in cautious["essential_w"]],
            nominal=[float(mission["essentialW"])] * len(bins),
        ),
    )
    chosen = planner.plan(cautious["solar_w"], cautious["essential_w"], mission)
    recorded = artifact["reference_plans"]["cautious"]
    if chosen.start_min != recorded["start_min"] or chosen.status != recorded["status"]:
        raise RuntimeError("planner does not reproduce the recorded Metis proposal")
    assert chosen.start_min is not None
    original_start = float(mission["originalBatch"][0])
    margins = planner.trajectories(
        cautious["solar_w"], cautious["essential_w"], [original_start, chosen.start_min], mission
    )
    original = planner.summary(
        cautious["solar_w"], cautious["essential_w"], original_start, mission
    )
    proposed = planner.summary(
        cautious["solar_w"], cautious["essential_w"], chosen.start_min, mission
    )
    crossing = original["crossing_min"]
    proposal = MetisProposal(
        proposal_id=hashlib.sha256(raw).hexdigest()[:16] + f"-{chosen.start_min:g}",
        task_id="compute_batch",
        from_start_min=original_start,
        to_start_min=chosen.start_min,
        status=chosen.status,
        rationale=(
            f"Under Metis's cautious forecast the batch at +{original_start:g} drains the battery: "
            f"it enters the protected reserve at +{crossing:.1f}, during the +100 to +103 "
            f"downlink. Moving the same 16-minute batch to +{chosen.start_min:g} keeps "
            f"{proposed['downlink_start_wh']:.2f} Wh above the reserve at the downlink start. It is "
            "the earliest start that never pushes the battery into the reserve."
        ),
        original_crossing_min=crossing,
        original_downlink_start_wh=float(original["downlink_start_wh"] or 0.0),
        proposed_downlink_start_wh=float(proposed["downlink_start_wh"] or 0.0),
        proposed_min_wh=float(proposed["min_wh"] or 0.0),
        original_margin=_series(margins[0], mission),
        proposed_margin=_series(margins[1], mission),
        alternatives=[
            Alternative(planner=label, start_min=plan.start_min, status=plan.status)
            for key, label in ALTERNATIVES
            for plan in [
                planner.plan(
                    artifact["mission_inputs"][key]["solar_w"],
                    artifact["mission_inputs"][key]["essential_w"],
                    mission,
                )
            ]
        ],
    )
    names = {
        "compute_batch": "Routine compute batch",
        "thermal_capture": "Thermal capture",
        "downlink": "Downlink to ground",
    }
    windows = {
        "compute_batch": (mission["originalBatch"], mission["batchW"], True),
        "thermal_capture": (mission["capture"], mission["captureW"], False),
        "downlink": (mission["downlink"], mission["radioW"], False),
    }
    brief = MissionBrief(
        title="Wildfire thermal delivery",
        request=(
            "A wildfire is approaching a town and a power corridor. The response team needs a "
            "fresh thermal image before its +120 briefing: capture at +90, downlink at +100."
        ),
        t0_utc=t0_utc,
        decision_min=-float(mission["commandLead"]),
        duration_min=float(mission["duration"]),
        tasks=[
            MissionTask(
                task_id=key,
                name=names[key],
                start_min=float(w[0]),
                end_min=float(w[1]),
                added_load_w=float(load),
                movable=movable,
            )
            for key, (w, load, movable) in windows.items()
        ],
        eclipses=[
            MissionInterval(start_min=float(a), end_min=float(b)) for a, b in mission["eclipses"]
        ],
        delivery_deadline_min=float(mission["deliveryDeadline"]),
        batch_deadline_min=float(mission["batchDeadline"]),
        reserve_wh=float(mission["initialMargin"]),
        environment_source=environment_source,
    )
    return Decision(mission=brief, forecast=forecast, proposal=proposal)
