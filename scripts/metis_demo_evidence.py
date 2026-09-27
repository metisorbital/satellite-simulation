"""Evidence that the Metis demo scenario tells the story in simulator physics.

Run from the repository root::

    uv run python scripts/metis_demo_evidence.py <demo_origin.json> [--start 122]

It flies three runs of ``configs/metis-wildfire.yaml`` in-process: the
original schedule (batch +70), the Metis plan (batch at ``--start``) and a
no-batch control. It prints the page's headline numbers and every task the
onboard start guard skipped, and compares margins with the page model under
the same truth (BUPT-1 realized solar, constant essential load). The original
run is compared only up to the downlink start, where its guard skips the
downlink and the page model does not. It exits non-zero if the story does not
hold. This is an evidence tool, not a test.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from metis_agent import planner
from metis_sim.adapters.configuration import load_configuration
from metis_sim.application.mission_run import build_mission_config
from metis_sim.models.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "configs/metis-wildfire.yaml"
FIXED = [
    {"task_id": "thermal_capture", "start_s": 5400, "end_s": 5490, "added_load_w": 20.0},
    {"task_id": "downlink", "start_s": 6000, "end_s": 6180, "added_load_w": 30.0},
]


def batch(start_min: float) -> dict:
    """Return the compute-batch window starting at a mission minute."""
    start_s = round(start_min * 60)
    return {
        "task_id": "compute_batch",
        "start_s": start_s,
        "end_s": start_s + 960,
        "added_load_w": 16.0,
    }


def summary(margin: np.ndarray) -> dict:
    """Headline numbers of a per-second margin series from mission minute 0."""
    below = np.flatnonzero(margin < 0)
    crossing = None
    if below.size:
        k = int(below[0])
        crossing = (k - 1 + margin[k - 1] / (margin[k - 1] - margin[k])) / 60
    return {
        "capture_end_wh": round(float(margin[5490]), 3),
        "downlink_start_wh": round(float(margin[6000]), 3),
        "downlink_end_wh": round(float(margin[6180]), 3),
        "min_wh": round(float(margin.min()), 3),
        "min_at_min": round(float(margin.argmin()) / 60, 2),
        "crossing_min": None if crossing is None else round(crossing, 2),
    }


def main() -> None:
    """Fly each plan, compare with the page model and report pass or fail."""
    parser = argparse.ArgumentParser()
    parser.add_argument("demo_origin")
    parser.add_argument("--start", type=float, default=122.0)
    args = parser.parse_args()
    template = load_configuration(TEMPLATE.read_text())
    plans = {
        "ORIGINAL": [batch(70), *FIXED],
        "METIS": [batch(args.start), *FIXED],
        "NOBATCH": FIXED,
    }
    profile = next(iter(template.profiles.values()))
    capacity = profile.battery.usable_capacity_wh
    threshold = profile.public_limits[0].value * capacity
    sim, skipped = {}, {}
    illumination: list[float] = []
    for name, windows in plans.items():
        config = build_mission_config(template, windows, name)
        engine = SimulationEngine(config).initialize()
        samples = [engine.sample(tick)[0] for tick in range(config.run.duration_s + 1)]
        sim[name] = summary(np.array([s.battery_energy_wh for s in samples]) - threshold)
        skipped[name] = [
            {
                "label": s.skipped_operation.label,
                "at_min": s.tick / 60,
                "battery_soc": round(s.skipped_operation.battery_soc, 4),
            }
            for s in samples
            if s.skipped_operation is not None
        ]
        illumination = [s.illumination_fraction for s in samples]

    demo = json.loads(Path(args.demo_origin).read_text())
    mission = planner.load_mission()
    solar = demo["sources"]["realized"]["solarW"]
    const = [profile.loads_w["nominal"]] * len(solar)
    page = {
        name: planner.summary(solar, const, start, mission)
        for name, start in (("ORIGINAL", 70.0), ("METIS", args.start), ("NOBATCH", None))
    }
    dark = np.array(illumination) < 0.5
    edges = np.flatnonzero(np.diff(dark.astype(int))) + 1
    report = {
        "eclipse_edges_min": [round(e / 60, 2) for e in edges.tolist()],
        "simulator": sim,
        "skipped_by_start_guard": skipped,
        "page_model_constant_load": {
            name: {
                k: (None if v is None else round(v, 3)) for k, v in p.items() if k != "start_min"
            }
            for name, p in page.items()
        },
    }
    compared = {
        "ORIGINAL": ("capture_end_wh", "downlink_start_wh"),
        "METIS": ("capture_end_wh", "downlink_start_wh", "downlink_end_wh", "min_wh"),
        "NOBATCH": ("capture_end_wh", "downlink_start_wh", "downlink_end_wh", "min_wh"),
    }
    worst = max(
        abs(sim[name][key] - page[name][key]) for name, keys in compared.items() for key in keys
    )
    original_skips = [item["label"] for item in skipped["ORIGINAL"]]
    checks = {
        "original enters the reserve before the +100 downlink": sim["ORIGINAL"]["crossing_min"]
        is not None
        and sim["ORIGINAL"]["crossing_min"] < 100,
        "original skips the downlink and nothing else": original_skips == ["downlink"],
        "Metis plan skips nothing": not skipped["METIS"],
        "Metis plan lowest margin >= +0.5 Wh": sim["METIS"]["min_wh"] >= 0.5,
        "no-batch lowest margin >= 0": sim["NOBATCH"]["min_wh"] >= 0,
        f"simulator within 0.1 Wh of the page model (worst {worst:.3f})": worst <= 0.1,
    }
    checks = {key: bool(value) for key, value in checks.items()}
    report["checks"] = checks
    print(json.dumps(report, indent=1))
    if not all(checks.values()):
        raise SystemExit("story does not hold")


if __name__ == "__main__":
    main()
