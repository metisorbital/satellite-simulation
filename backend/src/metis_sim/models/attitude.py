"""Orbit-derived ideal LVLH orientation and centered dipole field telemetry.

Every output is an instantaneous endpoint quantity at the supplied geometry's
epoch. The model has no clock or integrated attitude state: the authoritative
orbit provides position, velocity, and acceleration at that same epoch.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from metis_sim.domain.attitude import AttitudeConfiguration
from metis_sim.models.constants import EARTH_RADIUS_M
from metis_sim.models.orbit import FloatArray

Vector3 = tuple[float, float, float]
Quaternion = tuple[float, float, float, float]
AttitudeValue = float | Vector3 | Quaternion


def _vector(values: FloatArray | Vector3, name: str) -> FloatArray:
    """Validate one finite vector without mutating its input.

    Parameters
    ----------
    values : array_like, shape (3,)
        Candidate Cartesian vector.
    name : str
        Quantity name for a validation diagnostic.

    Returns
    -------
    ndarray, shape (3,)
        Finite float64 components, potentially sharing input storage.
    """
    result = np.asarray(values, dtype=np.float64)
    if result.shape != (3,) or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must contain three finite Cartesian components.")
    return result


def _tuple3(values: FloatArray) -> Vector3:
    """Detach three scalar components from an internal calculation buffer.

    Parameters
    ----------
    values : ndarray, shape (3,)
        Computed vector components.

    Returns
    -------
    tuple of float
        Immutable vector independent of the calculation buffer.
    """
    return float(values[0]), float(values[1]), float(values[2])


def _quaternion(rotation: FloatArray) -> Quaternion:
    """Convert a proper rotation to a canonical Hamilton wxyz quaternion.

    Parameters
    ----------
    rotation : ndarray, shape (3, 3)
        Proper orthonormal matrix mapping body vectors into GCRS.

    Returns
    -------
    tuple of float
        Unit quaternion in scalar-first order, with positive first nonzero
        component to select a deterministic representative of q and -q.
    """
    trace = float(np.trace(rotation))
    if trace > 0.0:
        scale = 2.0 * np.sqrt(1.0 + trace)
        values = np.array(
            [
                0.25 * scale,
                (rotation[2, 1] - rotation[1, 2]) / scale,
                (rotation[0, 2] - rotation[2, 0]) / scale,
                (rotation[1, 0] - rotation[0, 1]) / scale,
            ]
        )
    else:
        # Choosing the largest diagonal avoids division by a small scalar
        # near half-turns. The other branches follow cyclic axis order.
        i = int(np.argmax(np.diag(rotation)))
        j, k = (i + 1) % 3, (i + 2) % 3
        scale = 2.0 * np.sqrt(1.0 + rotation[i, i] - rotation[j, j] - rotation[k, k])
        values = np.empty(4, dtype=np.float64)
        values[0] = (rotation[k, j] - rotation[j, k]) / scale
        values[i + 1] = 0.25 * scale
        values[j + 1] = (rotation[j, i] + rotation[i, j]) / scale
        values[k + 1] = (rotation[k, i] + rotation[i, k]) / scale
    values /= np.linalg.norm(values)
    first_nonzero = values[np.flatnonzero(values)[0]]
    if first_nonzero < 0.0:
        values = -values
    return float(values[0]), float(values[1]), float(values[2]), float(values[3])


@dataclass(frozen=True, slots=True)
class AttitudeModel:
    """Calculate prescribed attitude measurements from one orbital state.

    Parameters
    ----------
    config : AttitudeConfiguration
        Frozen model identifiers and magnetic reference strength.

    Notes
    -----
    The ideal body orientation equals its nadir target exactly. The reported
    zero pointing error is an explicit prescription, not evidence of an ADCS
    controller's performance. Body angular velocity follows analytic
    derivatives of the LVLH axes, including changes in the orbital normal
    caused by the supplied acceleration. No finite differencing, sensor
    noise, controller, gyro bias, or actuator model is introduced.

    A Sun direction is geometrical and remains defined during eclipse; it
    must not be represented as a detected Sun-sensor signal in full shadow.
    The body magnetic vector is a noiseless sample of the declared axial
    dipole approximation, not a reconstruction of real mission measurements.
    """

    config: AttitudeConfiguration

    def step(
        self,
        *,
        position_gcrs_m: FloatArray | Vector3,
        velocity_gcrs_m_s: FloatArray | Vector3,
        acceleration_gcrs_m_s2: FloatArray | Vector3,
        sun_gcrs_m: FloatArray | Vector3,
        earth_pole_gcrs: FloatArray | Vector3,
    ) -> dict[str, AttitudeValue]:
        """Return instantaneous attitude and field channels without advancing time.

        Parameters
        ----------
        position_gcrs_m, velocity_gcrs_m_s, acceleration_gcrs_m_s2 : array_like, shape (3,)
            Authoritative GCRS position, velocity, and acceleration at one
            simulation endpoint, in metres, metres/second, and metres/second
            squared. Use the same force model as the orbit integrator.
        sun_gcrs_m : array_like, shape (3,)
            Geocentric GCRS Sun position in metres at that endpoint.
        earth_pole_gcrs : array_like, shape (3,)
            Unit terrestrial north-pole axis in GCRS at the run epoch,
            held fixed over the short arc as in the J2 orbit model.

        Returns
        -------
        dict of str to float or tuple of float
            Detached scalar or immutable vector/quaternion channel values.
            Quaternion order is wxyz, actively mapping body into GCRS;
            angular rate is body relative to GCRS, expressed in body axes,
            in radians/second. Field is in tesla, directions are unitless,
            and off-nadir/control errors are ideal prescribed degrees.

        Raises
        ------
        ValueError
            A vector is nonfinite or malformed, position intersects Earth,
            the orbital angular momentum vanishes, the Sun direction is
            undefined, or the Earth-pole input is not a unit vector.

        Notes
        -----
        Let r_hat=r/|r| and h_hat=(r cross v)/|r cross v|. Then the body
        basis in GCRS is z=-r_hat, y=-h_hat, x=y cross z. Differentiate
        normalized vectors with u_dot=(v_dot-u*(u dot v_dot))/|v| and use
        h_dot=r cross a. For a rotating orthonormal basis e_i,
        omega_GCRS=0.5*sum(e_i cross e_i_dot); transform by R.T for body
        components. This retains J2 nodal motion from the orbit model.

        The centered magnetic dipole uses m_hat=-earth_pole_gcrs and
        B=B_eq*(R_E/|r|)^3*(3*(m_hat dot r_hat)*r_hat-m_hat), calculated
        entirely in GCRS before the same R.T transformation into body axes.
        The sign gives an inward field near terrestrial geographic north.
        """
        position = _vector(position_gcrs_m, "Position")
        velocity = _vector(velocity_gcrs_m_s, "Velocity")
        acceleration = _vector(acceleration_gcrs_m_s2, "Acceleration")
        sun_position = _vector(sun_gcrs_m, "Sun position")
        pole = _vector(earth_pole_gcrs, "Earth pole")
        if not np.isclose(np.linalg.norm(pole), 1.0, rtol=0.0, atol=1e-12):
            raise ValueError("Earth pole must be a unit vector in GCRS.")
        radius = float(np.linalg.norm(position))
        if radius <= EARTH_RADIUS_M:
            raise ValueError("Earth-intersecting positions have no supported LVLH attitude.")
        momentum = np.cross(position, velocity)
        momentum_norm = float(np.linalg.norm(momentum))
        if momentum_norm <= 1e-12 * radius * float(np.linalg.norm(velocity)):
            raise ValueError("LVLH attitude requires a nonradial orbital velocity.")
        radial = position / radius
        normal = momentum / momentum_norm
        z_axis = -radial
        y_axis = -normal
        x_axis = np.cross(y_axis, z_axis)
        rotation = np.column_stack((x_axis, y_axis, z_axis))
        z_rate = -(velocity - radial * np.dot(radial, velocity)) / radius
        momentum_rate = np.cross(position, acceleration)
        y_rate = -(momentum_rate - normal * np.dot(normal, momentum_rate)) / momentum_norm
        x_rate = np.cross(y_rate, z_axis) + np.cross(y_axis, z_rate)
        omega_gcrs = 0.5 * (
            np.cross(x_axis, x_rate) + np.cross(y_axis, y_rate) + np.cross(z_axis, z_rate)
        )
        sun_delta = sun_position - position
        sun_distance = float(np.linalg.norm(sun_delta))
        if sun_distance == 0.0:
            raise ValueError("Satellite-to-Sun direction cannot be zero.")
        sun_body = rotation.T @ (sun_delta / sun_distance)
        moment_direction = -pole
        field_gcrs = (
            self.config.equatorial_field_t
            * (EARTH_RADIUS_M / radius) ** 3
            * (3.0 * np.dot(moment_direction, radial) * radial - moment_direction)
        )
        quaternion = _quaternion(rotation)
        return {
            "adcs.attitude_quaternion": quaternion,
            "adcs.target_quaternion": quaternion,
            "adcs.angular_velocity_rad_s": _tuple3(rotation.T @ omega_gcrs),
            "adcs.sun_vector_body": _tuple3(sun_body),
            "adcs.magnetic_field_body_t": _tuple3(rotation.T @ field_gcrs),
            "adcs.off_nadir_angle_deg": 0.0,
            "adcs.control_error_deg": 0.0,
            "orbit.position_gcrs_m": _tuple3(position),
            "orbit.velocity_gcrs_m_s": _tuple3(velocity),
        }
