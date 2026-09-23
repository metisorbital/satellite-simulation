"""Float64 fixed-step propagation under central Earth gravity and J2."""

from __future__ import annotations

from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from metis_sim.models.constants import EARTH_RADIUS_M, J2, MU_M3_S2

FloatArray = NDArray[np.float64]


class ClassicalElements(Protocol):
    """Structural input contract for osculating GCRS orbital elements.

    Attributes
    ----------
    a_m, e : float
        Semi-major axis in metres and dimensionless eccentricity.
    i_deg, raan_deg, argp_deg, true_anomaly_deg : float
        Inclination, node, periapsis, and true anomaly in degrees.
    """

    a_m: float
    e: float
    i_deg: float
    raan_deg: float
    argp_deg: float
    true_anomaly_deg: float


def elements_to_cartesian(elements: ClassicalElements) -> FloatArray:
    """Convert osculating two-body elements to a GCRS initial state.

    Parameters
    ----------
    elements : ClassicalElements
        Elements referenced to the GCRS XY plane and positive X direction.

    Returns
    -------
    ndarray, shape (6,)
        Float64 position in metres followed by velocity in metres/second.
    """
    i, node, peri, anomaly = np.deg2rad(
        [elements.i_deg, elements.raan_deg, elements.argp_deg, elements.true_anomaly_deg]
    )
    p = elements.a_m * (1.0 - elements.e * elements.e)
    radius = p / (1.0 + elements.e * np.cos(anomaly))
    position = radius * np.array([np.cos(anomaly), np.sin(anomaly), 0.0])
    velocity = np.sqrt(MU_M3_S2 / p) * np.array(
        [-np.sin(anomaly), elements.e + np.cos(anomaly), 0.0]
    )
    cn, sn, ci, si, cp, sp = (
        np.cos(node),
        np.sin(node),
        np.cos(i),
        np.sin(i),
        np.cos(peri),
        np.sin(peri),
    )
    rotation = np.array(
        [
            [cn * cp - sn * sp * ci, -cn * sp - sn * cp * ci, sn * si],
            [sn * cp + cn * sp * ci, -sn * sp + cn * cp * ci, -cn * si],
            [sp * si, cp * si, ci],
        ],
        dtype=np.float64,
    )
    return np.concatenate((rotation @ position, rotation @ velocity))


def acceleration(position_m: FloatArray, pole_gcrs: FloatArray, j2: float = J2) -> FloatArray:
    """Evaluate central gravity plus J2 about the fixed terrestrial pole.

    Parameters
    ----------
    position_m : ndarray, shape (..., 3)
        Geocentric inertial positions in metres.
    pole_gcrs : ndarray, shape (3,)
        Unit terrestrial north-pole axis at the run epoch in GCRS.
    j2 : float, optional
        Oblateness coefficient; zero is reserved for analytic test mode.

    Returns
    -------
    ndarray
        Accelerations in metres/second squared with the input shape.
    """
    radius2 = np.sum(position_m * position_m, axis=-1, keepdims=True)
    radius = np.sqrt(radius2)
    z = np.sum(position_m * pole_gcrs, axis=-1, keepdims=True)
    central = -MU_M3_S2 * position_m / (radius2 * radius)
    coefficient = 1.5 * j2 * MU_M3_S2 * EARTH_RADIUS_M**2 / (radius2**2 * radius)
    return central + coefficient * (
        (5.0 * z * z / radius2 - 1.0) * position_m - 2.0 * z * pole_gcrs
    )


def rk4_step(state: FloatArray, dt_s: float, pole_gcrs: FloatArray, j2: float = J2) -> FloatArray:
    """Advance one immutable state with classical fourth-order Runge-Kutta.

    Parameters
    ----------
    state : ndarray, shape (..., 6)
        Float64 Cartesian positions followed by velocities.
    dt_s : float
        Fixed physical time step in seconds.
    pole_gcrs : ndarray, shape (3,)
        Fixed unit symmetry axis.
    j2 : float, optional
        Oblateness coefficient, zero only for verification fixtures.

    Returns
    -------
    ndarray
        New state with no mutation of the input.
    """
    r, v = state[..., :3], state[..., 3:]
    k1r, k1v = v, acceleration(r, pole_gcrs, j2)
    k2r = v + 0.5 * dt_s * k1v
    k2v = acceleration(r + 0.5 * dt_s * k1r, pole_gcrs, j2)
    k3r = v + 0.5 * dt_s * k2v
    k3v = acceleration(r + 0.5 * dt_s * k2r, pole_gcrs, j2)
    k4r = v + dt_s * k3v
    k4v = acceleration(r + dt_s * k3r, pole_gcrs, j2)
    result = np.empty_like(state, dtype=np.float64)
    result[..., :3] = r + (dt_s / 6.0) * (k1r + 2.0 * k2r + 2.0 * k3r + k4r)
    result[..., 3:] = v + (dt_s / 6.0) * (k1v + 2.0 * k2v + 2.0 * k3v + k4v)
    return result


def propagate(
    initial_state: FloatArray,
    duration_s: int,
    pole_gcrs: FloatArray,
    *,
    dt_s: float = 1.0,
    j2: float = J2,
) -> FloatArray:
    """Precompute an inclusive, read-only fixed-step trajectory.

    Parameters
    ----------
    initial_state : ndarray, shape (..., 6)
        One state or an independent batch of satellite states.
    duration_s : int
        Positive elapsed SI seconds to propagate.
    pole_gcrs : ndarray, shape (3,)
        Earth symmetry axis fixed at the initial epoch.
    dt_s : float, optional
        One second in production; half a second in convergence tests.
    j2 : float, optional
        Production WGS84 J2, or zero for the two-body test case.

    Returns
    -------
    ndarray
        States including both t=0 and the final endpoint, with a leading
        time dimension. The returned buffer cannot be mutated.
    """
    if dt_s <= 0 or duration_s < 0 or not np.isclose(duration_s / dt_s, round(duration_s / dt_s)):
        raise ValueError("Duration must contain an integer number of positive time steps.")
    initial = np.asarray(initial_state, dtype=np.float64)
    if initial.shape[-1] != 6 or not np.all(np.isfinite(initial)):
        raise ValueError("Orbit state must contain six finite Cartesian components.")
    pole = np.asarray(pole_gcrs, dtype=np.float64)
    if pole.shape != (3,) or not np.isclose(np.linalg.norm(pole), 1.0, atol=1e-12):
        raise ValueError("J2 symmetry axis must be a finite unit vector.")
    count = round(duration_s / dt_s)
    states = np.empty((count + 1, *initial.shape), dtype=np.float64)
    states[0] = initial
    for index in range(count):
        states[index + 1] = rk4_step(states[index], dt_s, pole, j2)
    states.setflags(write=False)
    return states


def hermite_midpoints(states: FloatArray, dt_s: float = 1.0) -> FloatArray:
    """Evaluate cubic Hermite dense states between adjacent RK4 endpoints.

    Parameters
    ----------
    states : ndarray, shape (time, ..., 6)
        One consistent RK4 trajectory including position and velocity.
    dt_s : float, optional
        Separation between adjacent endpoint states in seconds.

    Returns
    -------
    ndarray
        Midpoint position and derivative; one fewer sample than endpoints.
    """
    left, right = states[:-1], states[1:]
    result = np.empty_like(left)
    result[..., :3] = 0.5 * (left[..., :3] + right[..., :3]) + (dt_s / 8.0) * (
        left[..., 3:] - right[..., 3:]
    )
    result[..., 3:] = 1.5 / dt_s * (right[..., :3] - left[..., :3]) - 0.25 * (
        left[..., 3:] + right[..., 3:]
    )
    return result
