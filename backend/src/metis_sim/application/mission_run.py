"""Demo-run configuration for one plan of the Metis wildfire mission.

The server-owned template flies one spacecraft with the original schedule.
A run moves each task window to the plan being flown, either the original
schedule or an operator-approved Metis plan. Everything else, including each
task's onboard start guard and the private scenario, stays as in the template.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from metis_sim.adapters.configuration import load_configuration
from metis_sim.domain.config import SimulationConfig


def build_mission_config(
    template: SimulationConfig, windows: Sequence[dict[str, Any]], name: str
) -> SimulationConfig:
    """Move the template's task windows to a plan's windows.

    Parameters
    ----------
    template : SimulationConfig
        Server-owned single-spacecraft template, including its private scenario.
    windows : sequence of dict
        Task windows, each with ``task_id``, ``start_s``, ``end_s`` and
        ``added_load_w``. ``task_id`` matches a template operation label.
    name : str
        Spacecraft display name for this run, such as ``Thermal imager · Metis plan``.

    Returns
    -------
    SimulationConfig
        Revalidated configuration. Each operation keeps its template mode and
        start guard.

    Raises
    ------
    ValueError
        If the template does not hold exactly one spacecraft, a window names
        an unknown task, or the windows fail validation (for example, overlap).
    """
    mapping = template.model_dump(mode="json")
    if len(mapping["satellites"]) != 1:
        raise ValueError("the mission template must hold exactly one spacecraft")
    satellite = mapping["satellites"][0]
    tasks = {operation["label"]: operation for operation in satellite["operations"]}
    unknown = {str(window["task_id"]) for window in windows} - set(tasks)
    if unknown:
        raise ValueError(f"unknown task labels: {sorted(unknown)}")
    satellite["name"] = name
    satellite["operations"] = [
        {
            **tasks[str(window["task_id"])],
            "start_s": int(window["start_s"]),
            "end_s": int(window["end_s"]),
            "repeat": None,
            "added_load_w": float(window["added_load_w"]),
        }
        for window in sorted(windows, key=lambda w: int(w["start_s"]))
    ]
    return load_configuration(json.dumps(mapping), "json")


__all__ = ["build_mission_config"]
