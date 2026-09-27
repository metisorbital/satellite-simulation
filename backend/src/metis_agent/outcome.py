"""Demo-run outcomes computed only from public telemetry, events and limits."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from metis_agent.models import MetisAlert, MinuteSeries, Plan, RunOutcome, TaskState, TaskWindow
from metis_agent.store import MetisError

FrameReader = Callable[[str, int, int], Sequence[Mapping[str, Any]]]
"""Read public frames for ``(satellite_id, from_sequence, through_sequence)``."""

EventReader = Callable[[str], Sequence[Mapping[str, Any]]]
"""Read the public operational events of ``satellite_id`` committed so far."""

MARGIN_STRIDE_S, SOLAR_STRIDE_S, PAGE = 6, 60, 2000


@dataclass
class _Run:
    energy: np.ndarray
    solar: np.ndarray
    next_sequence: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


class OutcomeTracker:
    """Incrementally read a demo run's frames and report its tasks and margin."""

    def __init__(self) -> None:
        self._runs: dict[str, _Run] = {}
        self._lock = threading.Lock()

    def forget(self, run_ids: Iterable[str]) -> None:
        """Drop cached frames of runs no longer shown.

        Parameters
        ----------
        run_ids : iterable of str
            Runs to forget.
        """
        with self._lock:
            for run_id in run_ids:
                self._runs.pop(run_id, None)

    def outcome(
        self,
        run_id: str,
        plan: Plan,
        name: str,
        status: Mapping[str, Any],
        tasks: Sequence[TaskWindow],
        read: FrameReader,
        events: EventReader,
        metis_on: bool = False,
        alert: MetisAlert | None = None,
    ) -> RunOutcome:
        """Return the run's outcome so far, reading only frames not yet seen.

        Parameters
        ----------
        run_id : str
            Demo run.
        plan : {"original", "metis"}
            Plan the run flies.
        name : str
            Plan display name.
        status : mapping
            Public run status with ``committed_tick``, ``duration_s``, ``status``
            and one entry in ``satellites`` (``capacity_wh`` and ``public_limits``).
        tasks : sequence of TaskWindow
            Task windows the run flies.
        read : callable
            Public frame reader.
        events : callable
            Public event reader.
        metis_on : bool, default=False
            Whether Metis watched the mission.
        alert : MetisAlert or None
            Metis's alert and decision for a watched mission.

        Returns
        -------
        RunOutcome
            Margin above the reserve and each task's progress.

        Raises
        ------
        MetisError
            ``not_mission_run`` when the run is not a single-spacecraft demo run.
        """
        if len(status["satellites"]) != 1:
            raise MetisError(
                "not_mission_run", "This run is not a Metis demo run; fly a plan first.", 409
            )
        craft = status["satellites"][0]
        satellite_id = str(craft["satellite_id"])
        capacity = float(craft["capacity_wh"])
        limit = next(item for item in craft["public_limits"] if item["operator"] == "lt")
        threshold = float(limit["value"]) * capacity
        duration = int(status["duration_s"])
        committed = int(status["committed_tick"])
        with self._lock:
            run = self._runs.setdefault(
                run_id, _Run(np.full(duration + 1, np.nan), np.full(duration + 1, np.nan))
            )
        with run.lock:
            while run.next_sequence <= committed:
                through = min(committed, run.next_sequence + PAGE - 1)
                for frame in read(satellite_id, run.next_sequence, through):
                    seq = int(frame["sequence"])
                    run.energy[seq] = frame["channels"]["eps.battery_energy_wh"]["value"]
                    run.solar[seq] = frame["channels"]["eps.solar_power_w"]["value"]
                run.next_sequence = through + 1
            energy, solar = run.energy.copy(), run.solar.copy()
        skipped = {
            (item["details"]["label"], int(item["details"]["start_s"]))
            for item in events(satellite_id)
            if item["event_type"] == "operation_skipped"
        }
        windows = {task.task_id: task for task in tasks}

        def state(task: TaskWindow) -> TaskState:
            if (task.task_id, task.start_s) in skipped:
                return "skipped"
            if committed < task.start_s:
                return "pending"
            return "running" if committed < task.end_s else "done"

        seen = max(committed, -1) + 1
        margin = energy[:seen] - threshold
        valid = np.isfinite(margin)
        negative = np.flatnonzero(valid & (margin < 0))
        low = int(np.nanargmin(margin)) if valid.any() else None

        def at(tick: int) -> float | None:
            return round(float(margin[tick]), 4) if tick < seen and valid[tick] else None

        capture, batch, downlink = (
            windows["thermal_capture"],
            windows["compute_batch"],
            windows["downlink"],
        )
        capture_state, downlink_state = state(capture), state(downlink)
        delivered = capture_state == "done" and downlink_state == "done"
        start_wh = at(downlink.start_s)
        ticks = np.arange(0, seen, MARGIN_STRIDE_S)
        minutes = range(seen // SOLAR_STRIDE_S)
        return RunOutcome(
            run_id=run_id,
            plan=plan,
            name=name,
            metis_on=metis_on,
            alert=alert,
            committed_min=round(max(committed, 0) / 60, 3),
            complete=status["status"] == "completed" or committed >= duration,
            threshold_wh=threshold,
            limit_soc=float(limit["value"]),
            batch_start_min=batch.start_s / 60,
            margin=MinuteSeries(
                minute=[round(t / 60, 3) for t in ticks.tolist()],
                value=[round(float(margin[t]), 4) for t in ticks],
            ),
            solar_w=MinuteSeries(
                minute=[m + 0.5 for m in minutes],
                value=[
                    round(float(np.nanmean(solar[m * 60 + 1 : (m + 1) * 60 + 1])), 3)
                    for m in minutes
                ],
            ),
            min_wh=None if low is None else round(float(margin[low]), 4),
            min_at_min=None if low is None else round(low / 60, 2),
            first_negative_min=round(int(negative[0]) / 60, 2) if negative.size else None,
            capture_end_wh=at(capture.end_s),
            downlink_start_wh=start_wh,
            downlink_end_wh=at(downlink.end_s),
            downlink_start_soc=None
            if start_wh is None
            else round((start_wh + threshold) / capacity, 4),
            capture=capture_state,
            batch=state(batch),
            downlink=downlink_state,
            downlink_progress=0.0
            if downlink_state in ("pending", "skipped")
            else round(
                min(1.0, (committed - downlink.start_s) / (downlink.end_s - downlink.start_s)), 4
            ),
            delivered_at_min=downlink.end_s / 60 if delivered else None,
        )
