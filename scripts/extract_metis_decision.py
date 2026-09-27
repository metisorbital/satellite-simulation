"""Copy an allowlisted Metis decision artifact into ``metis_agent``.

Run from the repository root::

    uv run python scripts/extract_metis_decision.py <demo_origin.json> <mission_scenario.json>

The source is the BUPT-1 walk-forward experiment's page payload. Only what
Metis knew at the decision time is kept: the forecast quantiles, the derived
mission-watt inputs, the mapping constants and the planner choices of each
input source. Every realized value, hindsight score and post-hoc note is
dropped, so the viewer cannot see the outcome before the simulator plays it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backend/src/metis_agent/data"
SOURCES = {
    "nominal": "nominal",
    "orbitRepeat": "orbit_repeat",
    "learnedMedian": "median",
    "learnedConservative": "cautious",
}


def extract(demo: dict) -> dict:
    """Return the allowlisted decision artifact.

    Parameters
    ----------
    demo : dict
        ``demo_origin.json`` from the walk-forward experiment.

    Returns
    -------
    dict
        Forecast and planner inputs available at the decision time.
    """
    raw = {
        target: {
            key: demo["raw"][source][key] for key in ("p10", "p50", "p90", "center", "orbitRepeat")
        }
        for target, source in (("solar_w", "solarW"), ("housekeeping_w", "housekeepingW"))
    }
    return {
        "source": {
            "dataset": "BUPT-1 (SatelliteCOTS release)",
            "decision_time": demo["originLabel"],
            "model_cutoff": demo["cutoff"],
            "last_training_origin": demo["training"]["lastTrainingOrigin"],
            "training_origins": demo["training"]["trainingOrigins"],
            "protocol": demo["protocol"],
            "lambda": demo["lambdaStar"],
            "centers": demo["selection"]["center"],
            "selection_window": demo["selection"]["window"],
        },
        "bin_minutes": demo["binMinutes"],
        "lead_minutes": demo["leadMinutes"],
        "bin_start_min": demo["binStartMission"],
        "mapping": demo["mapping"],
        "raw": {
            target: {("orbit_repeat" if k == "orbitRepeat" else k): v for k, v in values.items()}
            for target, values in raw.items()
        },
        "mission_inputs": {
            name: {
                "solar_w": demo["sources"][key]["solarW"],
                "essential_w": demo["sources"][key]["essentialW"],
            }
            for key, name in SOURCES.items()
        },
        "reference_plans": {
            name: {
                "start_min": demo["planner"][key]["start"],
                "status": demo["planner"][key]["status"],
            }
            for key, name in SOURCES.items()
        },
    }


def main() -> None:
    """Write the artifact and the mission constants."""
    demo = json.loads(Path(sys.argv[1]).read_text())
    mission = json.loads(Path(sys.argv[2]).read_text())
    artifact = extract(demo)
    text = json.dumps(artifact, indent=1)
    for banned in ("realized", "expected", "hindsight", "originChoice", "picked after"):
        assert banned not in text, banned
    OUT.mkdir(parents=True, exist_ok=True)
    stamp = demo["originLabel"].replace("-", "").replace(" ", "T").replace(":", "")
    (OUT / f"decision-bupt1-{stamp}.json").write_text(text + "\n")
    (OUT / "mission.json").write_text(json.dumps(mission, indent=1) + "\n")
    print(
        json.dumps(
            {"artifact": f"decision-bupt1-{stamp}.json", "bins": len(artifact["bin_start_min"])}
        )
    )


if __name__ == "__main__":
    main()
