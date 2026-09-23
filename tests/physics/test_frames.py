"""Published SOFA fixture and independent rotating-velocity verification."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
from astropy.time import Time
from metis_sim.models.constants import EARTH_RADIUS_M, MU_M3_S2
from metis_sim.models.frames import EarthOrientationError, FrameAdapter


def test_production_adapter_matches_published_sofa_fixture() -> None:
    """Compare P-04 to fixed published values rather than a self-generated matrix."""
    fixture = json.loads((Path(__file__).parent / "fixtures/sofa_c2t06a.json").read_text())
    position = np.array(fixture["position_m"])
    expected = np.array(fixture["expected_matrix"])
    transformed, matrix = FrameAdapter.explicit_earth_orientation(
        position,
        **{
            key: fixture[key]
            for key in ("tt_jd1", "tt_jd2", "ut1_jd1", "ut1_jd2", "xp_rad", "yp_rad")
        },
    )
    np.testing.assert_allclose(matrix, expected, rtol=0, atol=1e-12)
    np.testing.assert_allclose(transformed, expected @ position, rtol=0, atol=0.01)


def test_utc_itrs_roundtrip_and_dense_velocity_across_day() -> None:
    """Check P-03 at 101 polar/dateline/day-boundary positions and two FD steps."""
    adapter = FrameAdapter(datetime(2026, 9, 20, 23, tzinfo=UTC), 86_400)
    times = np.linspace(1.0, 86_399.0, 101)
    radius = EARTH_RADIUS_M + 550_000.0
    frequency = np.sqrt(MU_M3_S2 / radius**3)
    # Independent exact polar two-body trajectory rotated away from X/Z axes.
    rotation = np.array([[0.6, 0, 0.8], [0.8, 0, -0.6], [0, 1, 0]])

    def analytic_states(elapsed: np.ndarray) -> np.ndarray:
        angle = frequency * elapsed
        position = radius * np.stack((np.cos(angle), np.sin(angle), np.zeros_like(angle)), axis=1)
        velocity = (
            radius
            * frequency
            * np.stack((-np.sin(angle), np.cos(angle), np.zeros_like(angle)), axis=1)
        )
        return np.concatenate((position @ rotation.T, velocity @ rotation.T), axis=1)

    inertial = analytic_states(times)
    terrestrial = adapter.transform_states(inertial, times)
    recovered = adapter.transform_states(terrestrial, times, inverse=True)
    position_error = np.linalg.norm(recovered[:, :3] - inertial[:, :3], axis=1).max()
    assert position_error <= 0.01
    errors = []
    for step in (0.1, 0.05):
        minus = adapter.transform_states(analytic_states(times - step), times - step)
        plus = adapter.transform_states(analytic_states(times + step), times + step)
        finite_difference = (plus[:, :3] - minus[:, :3]) / (2 * step)
        error = np.linalg.norm(finite_difference - terrestrial[:, 3:], axis=1).max()
        errors.append(error)
        assert error <= 0.02
    print(f"P-03 roundtrip={position_error:.9g} m velocity h=.1/.05={errors} m/s")
    assert adapter.provenance["coverage_validated"]
    assert adapter.provenance["network_updates"] is False
    assert len(adapter.provenance["iers_sha256"]) == 64
    # LeapSeconds expires is stored with a date-only display format. Preserve
    # the actual UTC time when converting its TAI midnight expiration.
    assert adapter.provenance["leap_seconds_expiry"] == "2027-06-27T23:59:23.000"


def test_wgs84_geodetic_known_longitude_and_pole() -> None:
    """Verify geodetic signs at a known east longitude and a polar point."""
    radius = EARTH_RADIUS_M + 550_000.0
    positions = np.array([[0.0, radius, 0.0], [0.0, -radius, 0.0], [0.0, 0.0, 7_000_000.0]])
    coordinates = FrameAdapter.geodetic(positions)
    np.testing.assert_allclose(coordinates[:2, 1], [90.0, -90.0], atol=1e-10)
    np.testing.assert_allclose(coordinates[:2, 2], 550_000.0, atol=1e-6)
    assert coordinates[2, 0] == pytest.approx(90.0)


def test_time_preflight_rejects_leap_span_and_missing_coverage() -> None:
    """Ensure unsupported time inputs fail instead of producing approximate rotation."""
    with pytest.raises(EarthOrientationError, match="leap-second insertion"):
        FrameAdapter(datetime(2016, 12, 31, 23, 59, 59, tzinfo=UTC), 2)
    with pytest.raises(EarthOrientationError, match="covered"):
        FrameAdapter(datetime(1970, 1, 1, tzinfo=UTC), 60)
    with pytest.raises(EarthOrientationError, match="expiry"):
        FrameAdapter(datetime(2035, 1, 1, tzinfo=UTC), 60)


def test_epoch_and_provenance_access_cannot_mutate_validated_frame_inputs() -> None:
    """Keep validated physical time fixed when callers edit exported objects.

    Notes
    -----
    Astropy Time is mutable even when its Python attribute is read-only, so
    callers must receive a detached epoch rather than the owned instance.
    """
    adapter = FrameAdapter(datetime(2026, 9, 21, tzinfo=UTC), 60)
    elapsed = np.array([0.0, 60.0])
    expected_times = adapter.datetimes(elapsed)
    expected_pole = adapter.pole_gcrs()
    expected_provenance = adapter.provenance

    exported_epoch = adapter.epoch
    exported_epoch[...] = Time("2026-09-22", scale="utc")
    exported_provenance = adapter.provenance
    exported_provenance["coverage_validated"] = False
    for name, value in (("epoch", exported_epoch), ("provenance", {})):
        with pytest.raises(AttributeError):
            setattr(adapter, name, value)

    assert adapter.datetimes(elapsed) == expected_times
    np.testing.assert_array_equal(adapter.pole_gcrs(), expected_pole)
    assert adapter.provenance == expected_provenance
