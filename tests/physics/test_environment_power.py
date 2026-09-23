"""Independent eclipse geometry and energy-conservation edge cases."""

from __future__ import annotations

import numpy as np
import pytest
from metis_sim.models.constants import AU_M, EARTH_RADIUS_M, MU_M3_S2, SUN_RADIUS_M
from metis_sim.models.environment import illumination_fraction, solar_generation_w
from metis_sim.models.power import allocate_power
from scipy.integrate import quad
from scipy.optimize import brentq


def test_finite_solar_disk_against_independent_area_quadrature() -> None:
    """Check P-05 full light, umbra, and grazing angular-disk overlap."""
    position = np.array([EARTH_RADIUS_M + 550_000.0, 0.0, 0.0])
    alpha = np.arcsin(EARTH_RADIUS_M / np.linalg.norm(position))
    beta = np.arcsin(SUN_RADIUS_M / AU_M)
    for offset in (-2.0, -0.8, 0.0, 0.8, 2.0):
        theta = alpha + offset * beta
        sun = position + AU_M * np.array([-np.cos(theta), np.sin(theta), 0.0])
        fraction = float(illumination_fraction(position, sun))

        def overlap_height(local_x: float, theta: float = theta) -> float:
            earth_x = theta + local_x
            if abs(earth_x) >= alpha:
                return 0.0
            return 2.0 * min(
                np.sqrt(max(0, beta**2 - local_x**2)),
                np.sqrt(max(0, alpha**2 - earth_x**2)),
            )

        crossing = (alpha**2 - beta**2 - theta**2) / (2 * theta)
        breakpoints = [point for point in (crossing, alpha - theta) if -beta < point < beta]
        overlap, _ = quad(
            overlap_height, -beta, beta, points=breakpoints, epsabs=1e-13, epsrel=1e-10
        )
        reference = 1 - overlap / (np.pi * beta**2)
        assert 0.0 <= fraction <= 1.0
        assert fraction == pytest.approx(reference, abs=1e-7)
        if offset == -2.0:
            assert fraction == 0.0
            generation, _ = solar_generation_w(
                position,
                sun,
                np.array(fraction),
                area_m2=0.9,
                efficiency=0.28,
                conversion_efficiency=0.95,
                irradiance_1au_w_m2=1361.0,
            )
            assert generation == 0.0
        if offset == 2.0:
            assert fraction == 1.0


def test_eclipse_entry_within_one_second_of_independent_geometric_root() -> None:
    """Bound P-05 tick-resolution eclipse onset against a solved contact time."""
    radius = EARTH_RADIUS_M + 550_000.0
    rate = np.sqrt(MU_M3_S2 / radius**3)
    sun = np.array([AU_M, 0.0, 0.0])

    def position(elapsed: np.ndarray) -> np.ndarray:
        return radius * np.stack(
            (np.cos(rate * elapsed), np.sin(rate * elapsed), np.zeros_like(elapsed)), axis=-1
        )

    def contact(elapsed: float) -> float:
        state = position(np.array(elapsed))
        delta = sun - state
        direction = delta / np.linalg.norm(delta)
        separation = np.arccos(np.dot(-state / radius, direction))
        return (
            separation
            - np.arcsin(EARTH_RADIUS_M / radius)
            - np.arcsin(SUN_RADIUS_M / np.linalg.norm(delta))
        )

    reference = brentq(contact, 0.0, np.pi / rate, xtol=1e-10)
    times = np.arange(0, int(np.pi / rate))
    fractions = illumination_fraction(position(times), sun)
    first_partial = int(np.flatnonzero(fractions < 1)[0])
    assert 0 <= first_partial - reference <= 1.0


@pytest.mark.parametrize("energy", [0.0, 0.0001, 50.0, 99.9999, 100.0])
@pytest.mark.parametrize(
    "generation,load", [(0.0, 300.0), (30.0, 200.0), (300.0, 20.0), (80.0, 80.0)]
)
@pytest.mark.parametrize("dt", [0.0, 1.0, 60.0])
def test_bus_and_energy_balances_at_limits(
    energy: float, generation: float, load: float, dt: float
) -> None:
    """Check P-06/P-12 full, empty, capped, and zero-window allocations.

    Parameters
    ----------
    energy, generation, load, dt : float
        Independent edge-case energy, bus generation/demand, and duration.
    """
    allocation = allocate_power(generation, load, energy, 100.0, 0.91, 0.95, 100.0, 150.0, dt)
    assert allocation.generation_w + allocation.battery_power_w == pytest.approx(
        allocation.served_w + allocation.curtailed_w, abs=1e-6
    )
    assert load == pytest.approx(allocation.served_w + allocation.unserved_w, abs=1e-6)
    assert allocation.energy_wh - energy == pytest.approx(
        (0.91 * allocation.charge_w - allocation.discharge_w / 0.95) * dt / 3600,
        abs=1e-8,
    )
    assert 0 <= allocation.energy_wh <= 100.0
    assert 0 <= allocation.charge_w <= 100.0
    assert 0 <= allocation.discharge_w <= 150.0
    assert min(allocation.charge_w, allocation.discharge_w) == 0.0
    if dt == 0:
        assert allocation.energy_wh == energy


def test_constant_100w_discharge_has_analytic_energy_loss() -> None:
    """Check P-07 signed discharge and the independent sixty-second integral."""
    energy = 50.0
    for _ in range(60):
        result = allocate_power(0.0, 100.0, energy, 100.0, 0.95, 0.95, 250.0, 300.0, 1.0)
        energy = result.energy_wh
        assert result.battery_power_w == 100.0
    assert 50.0 - energy == pytest.approx(100 * 60 / (3600 * 0.95), abs=1e-6)


def test_empty_and_full_boundaries_use_average_power_without_clipping_loss() -> None:
    """Verify a battery that runs out halfway through the interval reports unmet load."""
    empty = allocate_power(0, 200, 0.025, 100, 1, 1, 500, 500, 1)
    assert empty.discharge_w == pytest.approx(90.0)
    assert empty.unserved_w == pytest.approx(110.0)
    assert empty.energy_wh == 0.0
    full = allocate_power(200, 0, 99.975, 100, 1, 1, 500, 500, 1)
    assert full.charge_w == pytest.approx(90.0)
    assert full.curtailed_w == pytest.approx(110.0)
    assert full.energy_wh == 100.0
