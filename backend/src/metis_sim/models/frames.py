"""Pinned offline Astropy time, Earth orientation, and frame conversion."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from threading import RLock

import astropy.units as u
import erfa
import numpy as np
from astropy.coordinates import (
    GCRS,
    ITRS,
    CartesianDifferential,
    CartesianRepresentation,
    EarthLocation,
    get_sun,
)
from astropy.time import Time, TimeDelta
from astropy.utils import iers

from metis_sim.models.orbit import FloatArray

_FRAME_LOCK = RLock()


class EarthOrientationError(ValueError):
    """Signal missing, expired, or unsupported pinned time/EOP inputs.

    Notes
    -----
    No approximate UTC rotation or live network refresh is substituted.
    """


class FrameAdapter:
    """Convert GCRS states using one pinned offline Earth-orientation table.

    Parameters
    ----------
    epoch_utc : datetime
        Timezone-aware UTC epoch for the run.
    duration_s : int
        Entire interval to validate before numerical propagation begins.

    Notes
    -----
    The installed, lockfile-pinned ``astropy-iers-data`` package supplies
    both finals2000A and leap-second inputs. Their byte checksums, coverage,
    and observed/predicted status are recorded in ``provenance``.
    """

    def __init__(self, epoch_utc: datetime, duration_s: int) -> None:
        iers.conf.auto_download = False
        iers.conf.auto_max_age = None
        iers.conf.iers_degraded_accuracy = "error"
        self._table_path = Path(iers.IERS_A_FILE)
        self._leap_path = Path(iers.IERS_LEAP_SECOND_FILE)
        self._table = iers.IERS_A.open(str(self._table_path))
        self._leaps = iers.LeapSeconds.open(str(self._leap_path))
        with _FRAME_LOCK:
            # Complete Astropy's one-time lazy leap-second initialization
            # offline before replacing ERFA's state with our pinned inputs.
            # A pre-existing cache must not silently become run provenance.
            _ = Time("2000-01-01", scale="utc").tai
            self._leaps.update_erfa_leap_seconds(initialize_erfa=True)
            self._epoch = Time(epoch_utc, scale="utc")
            end = (self._epoch.tai + TimeDelta(duration_s, format="sec")).utc
            if end >= self._leaps.expires:
                raise EarthOrientationError(
                    "The run extends beyond the pinned leap-second table expiry."
                )
            transition_mjd = np.asarray(self._leaps["mjd"], dtype=np.float64)
            spans_transition = np.any(
                (transition_mjd > self._epoch.utc.mjd) & (transition_mjd <= end.utc.mjd)
            )
            if spans_transition or ":60" in str(end.utc.isot):
                raise EarthOrientationError(
                    "Runs spanning leap-second insertion are unsupported by telemetry.v1."
                )
            checks = self.times(np.array([0.0, float(duration_s)]))
            _, ut_status = self._table.ut1_utc(checks, return_status=True)
            _, _, pm_status = self._table.pm_xy(checks, return_status=True)
            statuses = np.concatenate((ut_status, pm_status))
            if np.any(statuses < 0):
                raise EarthOrientationError(
                    "The entire run must be covered by the pinned IERS table."
                )
        self._provenance: dict[str, object] = {
            "frame": "ITRS",
            "inertial_frame": "GCRS",
            "earth_orientation_source": "astropy-iers-data/finals2000A.all",
            "iers_sha256": hashlib.sha256(self._table_path.read_bytes()).hexdigest(),
            "leap_seconds_sha256": hashlib.sha256(self._leap_path.read_bytes()).hexdigest(),
            "iers_first_mjd": float(self._table["MJD"][0].value),
            "iers_last_mjd": float(self._table["MJD"][-1].value),
            "iers_values": "predicted"
            if np.any(statuses == iers.FROM_IERS_A_PREDICTION)
            else "observed",
            "leap_seconds_expiry": str(self._leaps.expires.utc.to_value("isot", subfmt="date_hms")),
            "coverage_validated": True,
            "network_updates": False,
            "time_advance_scale": "TAI",
            "astropy_version": version("astropy"),
            "astropy_iers_data_version": version("astropy-iers-data"),
            "erfa_version": version("pyerfa"),
            "numpy_version": version("numpy"),
        }

    @property
    def epoch(self) -> Time:
        """Return a detached copy of the validated run epoch.

        Returns
        -------
        Time
            UTC epoch whose mutable Astropy state is owned by the caller.
        """
        return self._epoch.copy()

    @property
    def provenance(self) -> dict[str, object]:
        """Return a detached snapshot of the pinned frame inputs.

        Returns
        -------
        dict
            Scalar provenance values that cannot modify this adapter.
        """
        return self._provenance.copy()

    @contextmanager
    def _context(self) -> Iterator[None]:
        with _FRAME_LOCK, iers.earth_orientation_table.set(self._table):
            yield

    def times(self, elapsed_s: FloatArray) -> Time:
        """Map elapsed SI seconds to UTC using a continuous TAI timeline.

        Parameters
        ----------
        elapsed_s : ndarray
            Elapsed seconds, including fractional times for dense geometry.

        Returns
        -------
        Time
            Astropy UTC instants with the elapsed array's shape.
        """
        return (self._epoch.tai + TimeDelta(elapsed_s, format="sec")).utc

    def datetimes(self, elapsed_s: FloatArray) -> tuple[datetime, ...]:
        """Return representable, timezone-aware UTC interchange timestamps.

        Parameters
        ----------
        elapsed_s : ndarray
            One-dimensional sequence of elapsed seconds.

        Returns
        -------
        tuple of datetime
            UTC timestamps; leap-second spans have already been rejected.
        """
        return tuple(self.times(elapsed_s).to_datetime(timezone=UTC))

    def pole_gcrs(self) -> FloatArray:
        """Calculate the epoch's terrestrial north-pole direction in GCRS.

        Returns
        -------
        ndarray, shape (3,)
            Unit axis held fixed for this short-arc J2 model.
        """
        with self._context():
            pole = (
                ITRS(
                    CartesianRepresentation(np.array([0.0, 0.0, 1.0]) * u.m),
                    obstime=self._epoch,
                )
                .transform_to(GCRS(obstime=self._epoch))
                .cartesian.xyz.to_value(u.m)
            )
        return np.asarray(pole / np.linalg.norm(pole), dtype=np.float64)

    def transform_states(
        self, states: FloatArray, elapsed_s: FloatArray, *, inverse: bool = False
    ) -> FloatArray:
        """Transform positions and their full differentials as one batch.

        Parameters
        ----------
        states : ndarray, shape (time, ..., 6)
            Cartesian positions and derivatives in GCRS (ITRS if inverse).
        elapsed_s : ndarray, shape (time,)
            Time assigned to each leading state sample.
        inverse : bool, optional
            Transform ITRS to GCRS for validation instead of GCRS to ITRS.

        Returns
        -------
        ndarray
            Positions and velocities in the target frame, including its
            rotation term. Shape matches ``states``.
        """
        times = self.times(elapsed_s).reshape((len(elapsed_s),) + (1,) * (states.ndim - 2))
        representation = CartesianRepresentation(
            np.moveaxis(states[..., :3], -1, 0) * u.m,
            differentials=CartesianDifferential(np.moveaxis(states[..., 3:], -1, 0) * u.m / u.s),
        )
        source, target = (ITRS, GCRS) if inverse else (GCRS, ITRS)
        with self._context():
            transformed = source(representation, obstime=times).transform_to(target(obstime=times))
        result = np.empty_like(states)
        result[..., :3] = np.moveaxis(transformed.cartesian.xyz.to_value(u.m), 0, -1)
        result[..., 3:] = np.moveaxis(
            transformed.cartesian.differentials["s"].d_xyz.to_value(u.m / u.s), 0, -1
        )
        return result

    def sun_positions(self, elapsed_s: FloatArray) -> tuple[FloatArray, FloatArray]:
        """Compute builtin geometric Sun vectors once for each shared time.

        Parameters
        ----------
        elapsed_s : ndarray, shape (time,)
            Shared endpoint and midpoint elapsed times.

        Returns
        -------
        tuple of ndarray
            Geocentric GCRS and ITRS Sun positions in metres.
        """
        times = self.times(elapsed_s)
        with self._context():
            sun = get_sun(times)
            terrestrial = sun.transform_to(ITRS(obstime=times))
        return (
            np.moveaxis(sun.cartesian.xyz.to_value(u.m), 0, -1),
            np.moveaxis(terrestrial.cartesian.xyz.to_value(u.m), 0, -1),
        )

    @staticmethod
    def geodetic(position_itrf_m: FloatArray) -> FloatArray:
        """Convert terrestrial positions to WGS84 geodetic coordinates.

        Parameters
        ----------
        position_itrf_m : ndarray, shape (..., 3)
            Earth-fixed Cartesian positions in metres.

        Returns
        -------
        ndarray, shape (..., 3)
            Latitude in degrees, longitude in [-180,180), and ellipsoidal
            altitude in metres; not spherical radial or terrain altitude.
        """
        location = EarthLocation.from_geocentric(
            position_itrf_m[..., 0], position_itrf_m[..., 1], position_itrf_m[..., 2], unit=u.m
        )
        lon, lat, alt = location.to_geodetic("WGS84")
        return np.stack(
            (lat.to_value(u.deg), (lon.to_value(u.deg) + 180.0) % 360.0 - 180.0, alt.to_value(u.m)),
            axis=-1,
        )

    @staticmethod
    def explicit_earth_orientation(
        positions_gcrs_m: FloatArray,
        *,
        tt_jd1: float,
        tt_jd2: float,
        ut1_jd1: float,
        ut1_jd2: float,
        xp_rad: float,
        yp_rad: float,
    ) -> tuple[FloatArray, FloatArray]:
        """Transform positions from explicitly supplied SOFA time/EOP inputs.

        Parameters
        ----------
        positions_gcrs_m : ndarray, shape (..., 3)
            Input positions for the independent published matrix fixture.
        tt_jd1, tt_jd2 : float
            Two-part terrestrial-time Julian date.
        ut1_jd1, ut1_jd2 : float
            Two-part UT1 Julian date.
        xp_rad, yp_rad : float
            Polar motion in radians, supplied without an IERS lookup.

        Returns
        -------
        tuple of ndarray
            Transformed ITRS positions and the IAU 2006/2000A rotation matrix.

        Notes
        -----
        This injection seam verifies the same ERFA celestial/terrestrial
        convention used by the UTC/Astropy adapter against published values;
        separate tests cover its real UTC/IERS lookup and differential path.
        """
        matrix = erfa.c2t06a(tt_jd1, tt_jd2, ut1_jd1, ut1_jd2, xp_rad, yp_rad)
        return np.asarray(positions_gcrs_m) @ matrix.T, matrix
