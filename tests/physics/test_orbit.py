"""Independent analytic and adaptive-integration numerical gates."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from metis_sim.models.constants import EARTH_RADIUS_M, J2, MU_M3_S2
from metis_sim.models.orbit import elements_to_cartesian, hermite_midpoints, propagate
from scipy.integrate import solve_ivp


@pytest.mark.slow
def test_circular_24h_matches_analytic_solution() -> None:
    """Check the P-01 24-hour central-force solution and energy invariant."""
    radius = EARTH_RADIUS_M + 550_000.0
    speed = np.sqrt(MU_M3_S2 / radius)
    initial = np.array([radius, 0, 0, 0, speed, 0], dtype=np.float64)
    states = propagate(initial, 86_400, np.array([0.0, 0.0, 1.0]), j2=0.0)
    time = np.arange(86_401)
    angle = np.sqrt(MU_M3_S2 / radius**3) * time
    expected_position = radius * np.stack(
        (np.cos(angle), np.sin(angle), np.zeros_like(angle)), axis=1
    )
    expected_velocity = speed * np.stack(
        (-np.sin(angle), np.cos(angle), np.zeros_like(angle)), axis=1
    )
    position_error = np.linalg.norm(states[:, :3] - expected_position, axis=1).max()
    velocity_error = np.linalg.norm(states[:, 3:] - expected_velocity, axis=1).max()
    energy = np.sum(states[:, 3:] ** 2, axis=1) / 2 - MU_M3_S2 / np.linalg.norm(
        states[:, :3], axis=1
    )
    drift = np.max(np.abs((energy - energy[0]) / energy[0]))
    print(
        f"P-01 24h position={position_error:.9g} m velocity={velocity_error:.9g} m/s energy_drift={drift:.9g}"
    )
    assert position_error <= 10.0
    assert velocity_error <= 0.02
    assert drift <= 1e-7


@pytest.mark.slow
def test_j2_24h_convergence_and_independent_dop853() -> None:
    """Check P-02 across circular, polar, retrograde, and eccentric cases."""
    pole = np.array([0.0026, 0.00003, 1.0])
    pole /= np.linalg.norm(pole)
    elements = [
        SimpleNamespace(
            a_m=6_928_137.0, e=0.0, i_deg=0.0, raan_deg=0.0, argp_deg=0.0, true_anomaly_deg=33.0
        ),
        SimpleNamespace(
            a_m=6_928_137.0,
            e=0.001,
            i_deg=97.6,
            raan_deg=17.0,
            argp_deg=21.0,
            true_anomaly_deg=123.0,
        ),
        SimpleNamespace(
            a_m=7_078_137.0,
            e=0.05,
            i_deg=179.0,
            raan_deg=53.0,
            argp_deg=89.0,
            true_anomaly_deg=231.0,
        ),
    ]
    initial = np.stack([elements_to_cartesian(item) for item in elements])
    full = propagate(initial, 86_400, pole)
    half = propagate(initial, 86_400, pole, dt_s=0.5)
    convergence = np.linalg.norm(full[..., :3] - half[::2, :, :3], axis=-1).max(axis=0)

    def derivative(_time: float, state: np.ndarray) -> np.ndarray:
        shaped = state.reshape(-1, 6)
        result = np.empty_like(shaped)
        for index, row in enumerate(shaped):
            position = row[:3]
            radius = np.linalg.norm(position)
            axial = np.dot(position, pole)
            perturbation = 1.5 * J2 * MU_M3_S2 * EARTH_RADIUS_M**2 / radius**5
            result[index, :3] = row[3:]
            result[index, 3:] = -MU_M3_S2 * position / radius**3 + perturbation * (
                (5 * (axial / radius) ** 2 - 1) * position - 2 * axial * pole
            )
        return result.ravel()

    reference = solve_ivp(
        derivative,
        (0.0, 86_400.0),
        initial.ravel(),
        method="DOP853",
        rtol=2e-13,
        atol=1e-8,
        dense_output=True,
    )
    assert reference.success
    independent = reference.sol(np.arange(86_401.0)).T.reshape(-1, len(elements), 6)
    adaptive_error = np.linalg.norm(full[..., :3] - independent[..., :3], axis=-1).max(axis=0)
    midpoint_error = np.linalg.norm(
        hermite_midpoints(full)[..., :3] - half[1::2, :, :3], axis=-1
    ).max(axis=0)
    print(
        f"P-02 24h dt convergence={convergence.tolist()} m DOP853={adaptive_error.tolist()} m midpoint={midpoint_error.tolist()} m"
    )
    assert np.all(convergence <= 10.0)
    assert np.all(adaptive_error <= 10.0)
    assert np.all(midpoint_error <= 10.0)
    assert not full.flags.writeable


def test_elements_preserve_nonsymmetric_initial_state() -> None:
    """Verify orthogonal node rotation without assuming an equatorial orbit."""
    elements = SimpleNamespace(
        a_m=7_000_000.0,
        e=0.0,
        i_deg=90.0,
        raan_deg=90.0,
        argp_deg=0.0,
        true_anomaly_deg=90.0,
    )
    state = elements_to_cartesian(elements)
    np.testing.assert_allclose(state[:3], [0, 0, 7_000_000], atol=1e-8)
    np.testing.assert_allclose(state[3:], [0, -np.sqrt(MU_M3_S2 / 7_000_000), 0], atol=1e-8)
