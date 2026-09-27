"""Mission energy budget and batch planner used by Metis.

A port of the BUPT-1 demo page kernel (``Metis_Data/BUPT-1/scripts/mission_budget.py``)
with the same floating-point operations in the same order, so the simulator
demo proposes exactly the slot the page shows. Inputs are per-bin arrays in
mission watts: bin ``b`` covers mission minutes ``[-lead + 5b, -lead + 5b + 5)``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any, Literal

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
PlanStatus = Literal["ok", "unavoidable_deficit", "no_safe_slot"]


@dataclass(frozen=True)
class Mission:
    """Assumed mission timeline and energy constants, in minutes, watts and Wh.

    Attributes
    ----------
    constants : dict
        The page's ``mission_scenario.json`` values, for example ``capture``,
        ``downlink``, ``eclipses``, ``batchW``, ``initialMargin`` and ``planner``.
    """

    constants: dict[str, Any]

    def __getitem__(self, key: str) -> Any:
        """Return one mission constant.

        Parameters
        ----------
        key : str
            Constant name from ``mission_scenario.json``.

        Returns
        -------
        Any
            The stored value.
        """
        return self.constants[key]

    @property
    def bins(self) -> int:
        """Return the number of forecast bins from mission ``-lead`` to the end.

        Returns
        -------
        int
            Bin count, 39 for the three-hour mission.
        """
        return round((self["commandLead"] + self["duration"]) / self["binMinutes"])


def load_mission() -> Mission:
    """Load the packaged mission constants.

    Returns
    -------
    Mission
        Constants copied from the page scenario.
    """
    text = resources.files("metis_agent").joinpath("data/mission.json").read_text()
    return Mission(json.loads(text))


def _steps(mission: Mission) -> dict[str, Any]:
    n = round(mission["duration"] / mission["step"])
    i = np.arange(n)
    t = (i + 0.5) * mission["step"]
    lead_steps = round(mission["commandLead"] / mission["step"])
    bin_steps = round(mission["binMinutes"] / mission["step"])

    def active(interval: list[float]) -> npt.NDArray[np.bool_]:
        return (t >= interval[0]) & (t < interval[1])

    eclipse = np.zeros(n, bool)
    for interval in mission["eclipses"]:
        eclipse |= active(interval)
    return {
        "n": n,
        "t": t,
        "x": np.round((i + 1) * mission["step"], 4),
        "bin": (i + lead_steps) // bin_steps,
        "eclipse": eclipse,
        "capture": active(mission["capture"]),
        "radio": active(mission["downlink"]),
    }


def candidate_starts(mission: Mission) -> FloatArray:
    """Return every batch start the planner may choose.

    Parameters
    ----------
    mission : Mission
        Mission constants.

    Returns
    -------
    numpy.ndarray
        Start minutes from release to the last start whose batch meets its deadline.
    """
    planner = mission["planner"]
    starts = np.arange(
        planner["release"], planner["lastStart"] + 1e-9, planner["stepMinutes"], dtype=float
    )
    return starts[starts + mission["batchMinutes"] <= mission["batchDeadline"] + 1e-9]


def trajectories(
    solar_w: npt.ArrayLike, essential_w: npt.ArrayLike, starts: npt.ArrayLike, mission: Mission
) -> FloatArray:
    """Integrate the margin for several batch starts under one set of inputs.

    Parameters
    ----------
    solar_w, essential_w : array_like
        Per-bin mission watts; solar is ignored during mission eclipse.
    starts : array_like
        Batch start minutes; ``NaN`` means no batch.
    mission : Mission
        Mission constants.

    Returns
    -------
    numpy.ndarray
        Margins in Wh above the protected reserve, shaped ``(starts, steps + 1)``
        at mission minutes ``0, step, ..., duration``.
    """
    steps = _steps(mission)
    solar = np.asarray(solar_w, float)
    essential = np.asarray(essential_w, float)
    lo = np.asarray(starts, float)
    hi = lo + mission["batchMinutes"]
    energy = np.full(lo.size, float(mission["initialMargin"]))
    out = [energy.copy()]
    eff, step, cap = mission["efficiency"], mission["step"], float(mission["maxMargin"])
    for i in range(steps["n"]):
        t, b = steps["t"][i], steps["bin"][i]
        compute = (t >= lo) & (t < hi)
        load = (
            essential[b]
            + np.where(compute, float(mission["batchW"]), 0.0)
            + (float(mission["captureW"]) if steps["capture"][i] else 0.0)
            + (float(mission["radioW"]) if steps["radio"][i] else 0.0)
        )
        sun = 0.0 if steps["eclipse"][i] else solar[b]
        net = sun - load
        energy = np.minimum(cap, energy + np.where(net >= 0, net * eff, net / eff) * step / 60)
        out.append(energy.copy())
    return np.stack(out, axis=-1)


@dataclass(frozen=True)
class Plan:
    """Planner decision for one set of inputs.

    Attributes
    ----------
    start_min : float or None
        Earliest safe batch start, or ``None`` when no start is safe.
    status : {"ok", "unavoidable_deficit", "no_safe_slot"}
        ``unavoidable_deficit`` means the no-batch budget itself goes below zero.
    no_batch_min_wh : float
        Lowest no-batch margin.
    """

    start_min: float | None
    status: PlanStatus
    no_batch_min_wh: float


def plan(solar_w: npt.ArrayLike, essential_w: npt.ArrayLike, mission: Mission) -> Plan:
    """Choose the earliest batch start that never deepens a deficit.

    Parameters
    ----------
    solar_w, essential_w : array_like
        Per-bin mission watts.
    mission : Mission
        Mission constants.

    Returns
    -------
    Plan
        The start is safe when its margin stays at or above
        ``min(0, no-batch margin) - tolerance`` at every step.
    """
    starts = candidate_starts(mission)
    margins = trajectories(solar_w, essential_w, np.concatenate([starts, [np.nan]]), mission)
    none = margins[-1]
    tol = mission["planner"]["tolerance"]
    ok = ~(margins[:-1, 1:] < np.minimum(0.0, none[1:])[None, :] - tol).any(axis=1)
    no_batch_min = float(none.min())
    if not ok.any():
        return Plan(None, "no_safe_slot", no_batch_min)
    status: PlanStatus = "unavoidable_deficit" if no_batch_min < 0 else "ok"
    return Plan(float(starts[int(ok.argmax())]), status, no_batch_min)


def crossing(margins: FloatArray, mission: Mission) -> float | None:
    """Return the first linearly interpolated zero crossing.

    Parameters
    ----------
    margins : numpy.ndarray
        One trajectory from :func:`trajectories`.
    mission : Mission
        Mission constants.

    Returns
    -------
    float or None
        Mission minute of the first crossing below zero.
    """
    x = np.round(np.arange(margins.size) * mission["step"], 4)
    below = np.flatnonzero(margins < 0)
    if not below.size:
        return None
    k = int(below[0])
    a, b = margins[k - 1], margins[k]
    return float(x[k - 1] + (x[k] - x[k - 1]) * a / (a - b))


def summary(
    solar_w: npt.ArrayLike, essential_w: npt.ArrayLike, start_min: float | None, mission: Mission
) -> dict[str, float | None]:
    """Return the page's headline numbers for one schedule.

    Parameters
    ----------
    solar_w, essential_w : array_like
        Per-bin mission watts.
    start_min : float or None
        Batch start, or ``None`` for no batch.
    mission : Mission
        Mission constants.

    Returns
    -------
    dict
        Margins at capture end, downlink start and end, the minimum, its time,
        the final margin and the first zero crossing.
    """
    start = np.nan if start_min is None else start_min
    m = trajectories(solar_w, essential_w, [start], mission)[0]

    def at(minute: float) -> float:
        return float(m[round(minute / mission["step"])])

    return {
        "start_min": start_min,
        "capture_end_wh": at(mission["capture"][1]),
        "downlink_start_wh": at(mission["downlink"][0]),
        "downlink_end_wh": at(mission["downlink"][1]),
        "min_wh": float(m.min()),
        "min_at_min": float(np.round(m.argmin() * mission["step"], 4)),
        "final_wh": float(m[-1]),
        "crossing_min": crossing(m, mission),
    }
