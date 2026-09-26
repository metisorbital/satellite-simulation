"""Immutable selections for the prescribed attitude and magnetic field models."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class AttitudeConfiguration(BaseModel):
    """Declare an ideal nadir attitude and a centered axial magnetic dipole.

    Attributes
    ----------
    type : str
        ``ideal_lvlh_v1`` prescribes the body axes: +Z toward Earth's center,
        +Y opposite the orbital angular momentum, and +X = +Y cross +Z.
        There is no attitude-control or actuator dynamics model.
    magnetic_model : str
        ``centered_axial_dipole_v1`` places a magnetic dipole at Earth's
        center, antiparallel to the terrestrial north pole fixed at the run
        epoch. Tilt, higher multipoles, secular changes, and space weather
        are excluded.
    equatorial_field_t : float
        Dipole field magnitude at the WGS84 equatorial reference radius in
        tesla. The default 30.6 microtesla is a declared reference strength,
        not a fit to the supplied spacecraft measurements or an IGRF model.

    Notes
    -----
    Quaternion outputs use Hamilton scalar-first ``(w, x, y, z)`` order and
    actively map body vectors into GCRS. The stateless attitude kernel chooses
    positive w, or the first nonzero vector component at w=0. Thus q and -q
    represent the same physical orientation, and its canonical output can
    change sign as a trajectory crosses a half-turn. A time-series composer
    can choose the equivalent sign nearest the preceding quaternion.

    References
    ----------
    NASA's Earth Fact Sheet lists a reference dipole strength of
    0.306 gauss times Earth-radius cubed, corresponding to the default
    equatorial surface strength used here:
    https://nssdc.gsfc.nasa.gov/planetary/factsheet/earthfact.html
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)

    type: Literal["ideal_lvlh_v1"] = "ideal_lvlh_v1"
    magnetic_model: Literal["centered_axial_dipole_v1"] = "centered_axial_dipole_v1"
    equatorial_field_t: Annotated[float, Field(gt=0, le=1e-3)] = 30.6e-6
