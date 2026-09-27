"""Generate ``configs/metis-wildfire.yaml`` for the Metis wildfire demo.

Run from the repository root::

    uv run python scripts/build_metis_scenario.py <demo_origin.json>

The mission clock is tick = 60 x mission minute, with T0 at tick 0. The script:

1. Calibrates a circular orbit so the simulator's own eclipses fall on the
   demo's assumed windows (mission 0 to 15, 75 to 110 and 170 onward).
2. Measures the healthy full-sun generation of the demo array.
3. Writes the private truth: a solar-derating scenario whose per-5-minute
   multiplier reproduces BUPT-1's realized harvest on 21 June 2023, scaled
   to this spacecraft, relative to the healthy array.
4. Sets the essential load to BUPT-1's realized mean, scaled the same way.

The template holds one spacecraft, ``SAT-1``, with the original schedule.
Every task carries an onboard start guard at 50% state of charge, the top of
the protected reserve: a task due while the battery is inside the reserve is
skipped. Each demo run moves these windows to the plan being flown.

The realized values are private scenario inputs. They reach the viewer only
through the physics they drive, never as numbers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from metis_sim.adapters.configuration import load_configuration
from metis_sim.models.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "configs/metis-wildfire.yaml"
EPOCH = "2023-06-21T13:05:00Z"
DURATION_S = 10_800
BIN_S = 300
# Public provenance shown to viewers: the source's name, never its values.
ENVIRONMENT_SOURCE = "BUPT-1 solar harvest, 21 June 2023 (scaled)"
# Top of the protected reserve: margin 0 on the Metis page.
RESERVE_SOC = 0.5
# Mission task windows in seconds from T0: batch +70 to +86, capture +90 to
# +91.5, downlink +100 to +103.
TASKS = [
    {
        "start_s": 4200,
        "end_s": 5160,
        "mode": "payload_active",
        "added_load_w": 16.0,
        "label": "compute_batch",
        "min_start_soc": RESERVE_SOC,
    },
    {
        "start_s": 5400,
        "end_s": 5490,
        "mode": "payload_active",
        "added_load_w": 20.0,
        "label": "thermal_capture",
        "min_start_soc": RESERVE_SOC,
    },
    {
        "start_s": 6000,
        "end_s": 6180,
        "mode": "payload_active",
        "added_load_w": 30.0,
        "label": "downlink",
        "min_start_soc": RESERVE_SOC,
    },
]
TARGET = {"exit_1": 900, "entry_2": 4500, "exit_2": 6600, "entry_3": 10200}


def config(
    orbit: dict[str, float], essential_w: float, points: list[dict] | None
) -> dict[str, Any]:
    """Build the demo configuration mapping.

    Parameters
    ----------
    orbit : dict
        Keplerian elements of the demo spacecraft.
    essential_w : float
        Constant essential load in watts.
    points : list of dict or None
        Private derating control points, or ``None`` for a healthy calibration run.

    Returns
    -------
    dict
        Mapping accepted by ``load_configuration``.
    """
    return {
        "schema_version": "simulation.v1",
        "run": {
            "epoch_utc": EPOCH,
            "duration_s": DURATION_S,
            "tick_s": 1,
            "telemetry_period_s": 1,
            "speed": 120,
            "seed": 20230621,
            "earth_model": "wgs84_j2_v1",
            "orbit_model": "j2_cartesian",
            "sun_model": "astropy_builtin",
            "environment_source": ENVIRONMENT_SOURCE,
        },
        "profiles": {
            "metis_wildfire": {
                "panel": {
                    "area_m2": 0.194,
                    "efficiency": 0.28,
                    "conversion_efficiency": 0.95,
                    "irradiance_1au_w_m2": 1361.0,
                    "pointing": {"type": "ideal_sun_tracking"},
                },
                "battery": {
                    "type": "energy_store",
                    "usable_capacity_wh": 19.0,
                    "initial_soc": 1.0,
                    "charge_efficiency": 0.95,
                    "discharge_efficiency": 0.95,
                    "max_charge_w": 100.0,
                    "max_discharge_w": 100.0,
                },
                "loads_w": {"nominal": essential_w, "payload_active": essential_w, "safe": 5.0},
                "sensors": {"catalog": "power-leo.v1", "noise": {"type": "none"}},
                "public_limits": [
                    {
                        "channel_id": "eps.battery_soc",
                        "operator": "lt",
                        "value": RESERVE_SOC,
                        "clear_value": RESERVE_SOC,
                    }
                ],
            }
        },
        "satellites": [
            {
                "satellite_id": "SAT-1",
                "name": "Thermal imager",
                "profile_id": "metis_wildfire",
                "orbit": dict(orbit),
                "initial_mode": "nominal",
                "operations": [dict(task) for task in TASKS],
                "visual": {"color": "#8FD3FF", "asset_id": None},
            }
        ],
        "constellations": [],
        "scenario": [
            {
                "satellite_id": "SAT-1",
                "type": "solar_derating",
                "points": points,
                "outcome": {
                    "type": "energy_reserve_violation",
                    "reserve_soc": RESERVE_SOC,
                    "dwell_s": 60,
                },
            }
        ]
        if points
        else [],
    }


def healthy_run(orbit: dict[str, float]) -> tuple[np.ndarray, np.ndarray]:
    """Return per-tick illumination and generation for the healthy spacecraft.

    Parameters
    ----------
    orbit : dict
        Keplerian elements to evaluate.

    Returns
    -------
    tuple of numpy.ndarray
        Illumination fraction and interval generation in watts per tick.
    """
    mapping = config(orbit, 8.0, None)
    mapping["satellites"][0]["operations"] = []
    engine = SimulationEngine(load_configuration(json.dumps(mapping), "json")).initialize()
    samples = [engine.sample(tick)[0] for tick in range(DURATION_S + 1)]
    return (
        np.array([s.illumination_fraction for s in samples]),
        np.array([s.solar_power_w for s in samples]),
    )


def eclipses(illumination: np.ndarray) -> dict[str, int]:
    """Locate eclipse edges where illumination crosses one half.

    Parameters
    ----------
    illumination : numpy.ndarray
        Per-tick illumination fraction.

    Returns
    -------
    dict
        Tick of the first exit and of the second and third entries and exits.
    """
    dark = illumination < 0.5
    edges = np.flatnonzero(np.diff(dark.astype(int)))
    entries = [int(e) + 1 for e in edges if not dark[e]]
    exits = [int(e) + 1 for e in edges if dark[e]]
    return {"exit_1": exits[0], "entry_2": entries[0], "exit_2": exits[1], "entry_3": entries[1]}


def calibrate() -> tuple[dict[str, float], dict[str, int], np.ndarray]:
    """Fit semi-major axis, RAAN and true anomaly to the target eclipse edges.

    Returns
    -------
    tuple
        Orbit, measured eclipse edges and healthy generation per tick.
    """
    orbit = {
        "a_m": 6_891_000.0,
        "e": 0.0,
        "i_deg": 97.6,
        "raan_deg": 72.0,
        "argp_deg": 0.0,
        "true_anomaly_deg": 211.7,
    }
    for _ in range(8):
        illumination, generation = healthy_run(orbit)
        edges = eclipses(illumination)
        period = edges["entry_3"] - edges["entry_2"]
        duration = edges["exit_2"] - edges["entry_2"]
        error = {k: edges[k] - TARGET[k] for k in TARGET}
        print(json.dumps({"orbit": orbit, "edges": edges, "error_s": error}), flush=True)
        if max(abs(v) for v in error.values()) <= 30:
            return orbit, edges, generation
        # Period from the semi-major axis, eclipse length from RAAN (beta angle),
        # phase from the true anomaly.
        orbit["a_m"] *= (1 + (5700 - period) / 5700) ** (2 / 3)
        orbit["raan_deg"] += (duration - 2100) / 60 * 0.6
        orbit["true_anomaly_deg"] = (
            orbit["true_anomaly_deg"] - error["exit_1"] / period * 360
        ) % 360
        orbit = {k: round(v, 3) for k, v in orbit.items()}
    raise SystemExit("eclipse calibration did not converge")


def main() -> None:
    """Calibrate, derive the private scenario and write the YAML."""
    demo = json.loads(Path(sys.argv[1]).read_text())
    orbit, edges, generation = calibrate()
    illumination, _ = healthy_run(orbit)
    full_sun = float(np.median(generation[illumination >= 0.999]))
    first = demo["binStartMission"].index(0)
    realized = demo["sources"]["realized"]
    solar = np.array(realized["solarW"][first:])
    essential_w = round(float(np.mean(realized["essentialW"][first:])), 1)
    multipliers = np.clip(solar / full_sun, 0.0, 1.0)
    points = []
    for k, m in enumerate(multipliers):
        points += [
            {"at_s": BIN_S * k, "multiplier": round(float(m), 6)},
            {"at_s": BIN_S * k + BIN_S - 1, "multiplier": round(float(m), 6)},
        ]
    mapping = config(orbit, essential_w, points)
    load_configuration(json.dumps(mapping), "json")
    header = (
        "# Generated by scripts/build_metis_scenario.py; do not edit by hand.\n"
        "# Metis wildfire demo template: SAT-1 with the original schedule; each run moves\n"
        "# the task windows to the plan flown. T0 = tick 0 = 2023-06-21 13:05 UTC.\n"
        f"# Eclipse edges (s): {edges}. Healthy full-sun array {full_sun:.2f} W.\n"
        "# The scenario block is private truth shaped from BUPT-1's realized 21 June 2023\n"
        "# harvest; it never reaches viewer or consumer data.\n"
    )
    OUT.write_text(
        header + yaml.safe_dump(mapping, sort_keys=False, default_flow_style=None, width=110)
    )
    print(
        json.dumps(
            {
                "file": str(OUT),
                "orbit": orbit,
                "edges": edges,
                "full_sun_w": full_sun,
                "essential_w": essential_w,
                "max_multiplier": float(multipliers.max()),
                "points": len(points),
            },
            indent=1,
        )
    )


if __name__ == "__main__":
    main()
