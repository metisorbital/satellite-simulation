"""Generate Cesium interpolation references from independent dense J2 dynamics."""

import json
from pathlib import Path

import numpy as np
from metis_sim.adapters.configuration import load_configuration
from metis_sim.models.constants import EARTH_RADIUS_M, J2, MU_M3_S2
from metis_sim.models.engine import SimulationEngine
from metis_sim.models.frames import FrameAdapter
from metis_sim.models.orbit import elements_to_cartesian
from scipy.integrate import solve_ivp


def main() -> None:
    """Write fixed endpoint samples and independent intermediate ITRS references."""
    raw = load_configuration(Path("configs/demo.yaml").read_text()).model_dump(mode="json")
    raw["run"]["duration_s"] = 600
    raw["scenario"] = []
    for satellite in raw["satellites"]:
        satellite["operations"] = []
    config = load_configuration(json.dumps(raw), "json")
    engine = SimulationEngine(config).initialize()
    frames = FrameAdapter(config.run.epoch_utc, 600)
    axis = frames.pole_gcrs()

    def derivative(elapsed_s: float, state: np.ndarray) -> np.ndarray:
        """Evaluate a separate reference expression for the fixed-axis J2 model.

        Parameters
        ----------
        elapsed_s : float
            Solver time, unused for this autonomous force law.
        state : numpy.ndarray
            Inertial Cartesian position and velocity in SI units.

        Returns
        -------
        numpy.ndarray
            Velocity followed by the reference gravitational acceleration.
        """
        position, velocity = state[:3], state[3:]
        radius = np.linalg.norm(position)
        height = np.dot(position, axis)
        acceleration = -MU_M3_S2 * position / radius**3
        acceleration += (1.5 * J2 * MU_M3_S2 * EARTH_RADIUS_M**2 / radius**5) * (
            (5 * height**2 / radius**2 - 1) * position - 2 * height * axis
        )
        return np.concatenate((velocity, acceleration))

    cases = []
    for satellite in config.satellites:
        reference = solve_ivp(
            derivative,
            (0, 600),
            elements_to_cartesian(satellite.orbit),
            method="DOP853",
            rtol=2e-13,
            atol=1e-9,
            dense_output=True,
        )
        assert reference.success and reference.sol is not None
        for tick in [0, 14, 69, 120, 301, 599]:
            elapsed = np.array([tick + 0.25, tick + 0.5, tick + 0.75])
            states = reference.sol(elapsed).T[:, None, :]
            terrestrial = frames.transform_states(states, elapsed)[:, 0, :]
            endpoints = engine.trajectory(satellite.satellite_id, tick, tick + 1, 1)
            cases.append(
                {
                    "satellite_id": satellite.satellite_id,
                    "endpoints": [
                        {
                            "at": sample.observed_at.isoformat(),
                            "position_m": sample.position_itrf_m,
                            "velocity_m_s": sample.velocity_itrf_m_s,
                        }
                        for sample in endpoints
                    ],
                    "references": [
                        {"at": at.isoformat(), "position_m": position[:3].tolist()}
                        for at, position in zip(frames.datetimes(elapsed), terrestrial, strict=True)
                    ],
                }
            )
    payload = {
        "reference": "SciPy DOP853 independent force expression; pinned production Earth orientation",
        "tolerance_m": 100,
        "sample_tolerance_m": 0.01,
        "provenance": engine.provenance,
        "cases": cases,
    }
    destination = Path("tests/fixtures/orbit-interpolation.json")
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"Saved {len(cases)} intervals / {sum(len(case['references']) for case in cases)} dense references"
    )


if __name__ == "__main__":
    main()
