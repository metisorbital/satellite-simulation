"""Bounded analytic orbit presentation from explicit mission configuration."""

import json
from datetime import datetime
from functools import lru_cache
from importlib.resources import files

import numpy as np

from metis_sim.domain.configured_orbit import ConfiguredOrbit
from metis_sim.domain.public import OrbitPoint
from metis_sim.models.constants import MU_M3_S2
from metis_sim.models.frames import FrameAdapter
from metis_sim.models.orbit import elements_to_cartesian


def default_bupt1_orbit(epoch_utc: datetime) -> ConfiguredOrbit:
    """Load sourced BUPT-1 orbit settings with an explicitly assumed epoch.

    Parameters
    ----------
    epoch_utc : datetime
        Archive start, used only to anchor the configured orbit's phase.

    Returns
    -------
    ConfiguredOrbit
        Validated published altitude/inclination and disclosed missing angles.
    """
    source = json.loads(files("metis_sim").joinpath("data/bupt1_orbit.json").read_text())
    return ConfiguredOrbit.model_validate({**source, "epoch_utc": epoch_utc})


@lru_cache(maxsize=4)
def _frames(epoch_utc: datetime, duration_s: int) -> FrameAdapter:
    return FrameAdapter(epoch_utc, duration_s)


def configured_orbit_points(
    configuration: ConfiguredOrbit,
    duration_s: int,
    start: int,
    end: int,
    step: int,
) -> list[OrbitPoint]:
    """Evaluate a bounded two-body trajectory directly at source-clock instants.

    Parameters
    ----------
    configuration : ConfiguredOrbit
        Frozen display-only orbital elements at the archive's original epoch.
    duration_s : int
        Full archive span, used to validate pinned Earth-orientation coverage.
    start, end : int
        Inclusive elapsed source-time bounds. The end is always included.
    step : int
        Positive sample spacing in source seconds.

    Returns
    -------
    list of OrbitPoint
        Earth-fixed positions and full rotating-frame velocity derivatives.

    Notes
    -----
    The service validates a maximum one-hour, 3601-point request before calling.
    Solving Kepler's equation at the requested instants avoids propagating all
    intervening seconds after a long seek. No EPS, observed telemetry, private
    truth, or orbital fit is computed. J2, drag and maneuvers are not modeled.
    """
    elapsed = np.arange(start, end + 1, step, dtype=np.float64)
    if elapsed[-1] != end:
        elapsed = np.append(elapsed, float(end))
    orbit = configuration.orbit
    mean_motion = np.sqrt(MU_M3_S2 / orbit.a_m**3)
    initial_true_anomaly = np.deg2rad(orbit.true_anomaly_deg)
    eccentric_factor = np.sqrt(1 - orbit.e**2)
    initial_eccentric_anomaly = np.arctan2(
        eccentric_factor * np.sin(initial_true_anomaly),
        orbit.e + np.cos(initial_true_anomaly),
    )
    initial_mean_anomaly = initial_eccentric_anomaly - orbit.e * np.sin(initial_eccentric_anomaly)
    mean_anomaly = np.remainder(initial_mean_anomaly + mean_motion * elapsed, 2 * np.pi)
    eccentric_anomaly = mean_anomaly.copy()
    for _ in range(8):
        correction = (eccentric_anomaly - orbit.e * np.sin(eccentric_anomaly) - mean_anomaly) / (
            1 - orbit.e * np.cos(eccentric_anomaly)
        )
        eccentric_anomaly -= correction
        if np.max(np.abs(correction)) < 1e-14:
            break
    if (
        np.max(np.abs(eccentric_anomaly - orbit.e * np.sin(eccentric_anomaly) - mean_anomaly))
        > 1e-12
    ):
        raise ValueError("Configured display orbit did not converge")
    periapsis = elements_to_cartesian(orbit.model_copy(update={"true_anomaly_deg": 0.0}))
    basis_p = periapsis[:3] / np.linalg.norm(periapsis[:3])
    basis_q = periapsis[3:] / np.linalg.norm(periapsis[3:])
    cosine, sine = np.cos(eccentric_anomaly)[:, None], np.sin(eccentric_anomaly)[:, None]
    positions = orbit.a_m * ((cosine - orbit.e) * basis_p + eccentric_factor * sine * basis_q)
    velocities = (
        orbit.a_m
        * mean_motion
        / (1 - orbit.e * cosine)
        * (-sine * basis_p + eccentric_factor * cosine * basis_q)
    )
    frames = _frames(configuration.epoch_utc, duration_s)
    states_itrs = frames.transform_states(np.concatenate((positions, velocities), axis=1), elapsed)
    times = frames.datetimes(elapsed)
    _, sun_itrs = frames.sun_positions(elapsed)
    rotations = frames.gcrs_to_itrs_rotations(elapsed)
    return [
        OrbitPoint(
            elapsed_s=int(tick),
            observed_at=at,
            position_itrs_m=tuple(state[:3]),
            velocity_itrs_m_s=tuple(state[3:]),
            sun_position_itrs_m=tuple(sun),
            gcrs_to_itrs_rotation=tuple(rotation.ravel()),
        )
        for tick, at, state, sun, rotation in zip(
            elapsed, times, states_itrs, sun_itrs, rotations, strict=True
        )
    ]
