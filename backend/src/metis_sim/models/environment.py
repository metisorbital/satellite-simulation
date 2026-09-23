"""Finite solar-disk occultation and prescribed ideal panel pointing."""

from __future__ import annotations

import numpy as np

from metis_sim.models.constants import AU_M, EARTH_RADIUS_M, SUN_RADIUS_M
from metis_sim.models.orbit import FloatArray


def illumination_fraction(position_m: FloatArray, sun_position_m: FloatArray) -> FloatArray:
    """Calculate visible solar area using angular disk overlap.

    Parameters
    ----------
    position_m : ndarray, shape (..., 3)
        Satellite geocentric GCRS position in metres.
    sun_position_m : ndarray, shape (..., 3)
        Broadcastable geocentric Sun position in the identical frame/time.

    Returns
    -------
    ndarray
        Fraction in [0,1], with exact zeros in full umbra.

    Notes
    -----
    Uses a spherical Earth and finite solar disk, with no atmosphere or
    refraction. Roundoff clamping only protects inverse trigonometry.
    """
    radius = np.linalg.norm(position_m, axis=-1)
    if np.any(radius <= EARTH_RADIUS_M):
        raise ValueError("Earth-intersecting positions have no supported eclipse geometry.")
    sun_delta = sun_position_m - position_m
    distance = np.linalg.norm(sun_delta, axis=-1)
    alpha = np.arcsin(EARTH_RADIUS_M / radius)
    beta = np.arcsin(SUN_RADIUS_M / distance)
    direction = sun_delta / distance[..., None]
    theta = np.arccos(np.clip(np.sum(-position_m / radius[..., None] * direction, axis=-1), -1, 1))
    result = np.ones_like(theta, dtype=np.float64)
    earth_contains = alpha >= theta + beta
    sun_contains = beta >= theta + alpha
    result = np.where(earth_contains, 0.0, result)
    result = np.where(sun_contains, 1.0 - (alpha / beta) ** 2, result)
    partial = (theta < alpha + beta) & ~earth_contains & ~sun_contains
    # Indexing first avoids division by zero in coincident/contained cases.
    a, b, d = alpha[partial], beta[partial], theta[partial]
    overlap = a * a * np.arccos(np.clip((d * d + a * a - b * b) / (2 * d * a), -1, 1))
    overlap += b * b * np.arccos(np.clip((d * d + b * b - a * a) / (2 * d * b), -1, 1))
    radical = (-d + a + b) * (d + a - b) * (d - a + b) * (d + a + b)
    overlap -= 0.5 * np.sqrt(np.maximum(radical, 0.0))
    result[partial] = np.clip(1.0 - overlap / (np.pi * b * b), 0.0, 1.0)
    return result


def panel_incidence_cosine(normal: FloatArray, sun_direction: FloatArray) -> FloatArray:
    """Retain the explicit pointing dot product for future panel policies.

    Parameters
    ----------
    normal, sun_direction : ndarray, shape (..., 3)
        Unit panel normal and satellite-to-Sun direction in one frame.

    Returns
    -------
    ndarray
        Nonnegative incidence cosine, bounded against floating roundoff.
    """
    return np.clip(np.sum(normal * sun_direction, axis=-1), 0.0, 1.0)


def solar_generation_w(
    position_m: FloatArray,
    sun_position_m: FloatArray,
    illumination: FloatArray,
    *,
    area_m2: float,
    efficiency: float,
    conversion_efficiency: float,
    irradiance_1au_w_m2: float,
) -> tuple[FloatArray, FloatArray]:
    """Compute healthy generation for the ideal two-axis equivalent array.

    Parameters
    ----------
    position_m, sun_position_m : ndarray, shape (..., 3)
        Satellite and Sun GCRS positions in metres at identical times.
    illumination : ndarray
        Visible solar fraction matching the position array.
    area_m2, efficiency, conversion_efficiency : float
        Equivalent installed area and panel/bus conversion efficiencies.
    irradiance_1au_w_m2 : float
        Fixed baseline irradiance, 1361 W/m² in the P0 model.

    Returns
    -------
    tuple of ndarray
        Healthy generated bus watts and endpoint panel incidence cosines.
    """
    delta = sun_position_m - position_m
    distance = np.linalg.norm(delta, axis=-1)
    direction = delta / distance[..., None]
    incidence = panel_incidence_cosine(direction, direction)
    generation = (
        irradiance_1au_w_m2
        * (AU_M / distance) ** 2
        * area_m2
        * efficiency
        * conversion_efficiency
        * incidence
        * illumination
    )
    return generation, incidence
