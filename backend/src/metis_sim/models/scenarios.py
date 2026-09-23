"""Private causal derating and state-driven reserve outcome evaluation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from metis_sim.models.orbit import FloatArray


class DeratingPoint(Protocol):
    """Structural contract for a private linear-ramp control point.

    Attributes
    ----------
    at_s : int
        Control-point time in elapsed simulated seconds.
    multiplier : float
        Available-generation multiplier in [0,1].
    """

    at_s: int
    multiplier: float


def derating_multipliers(times_s: FloatArray, points: Sequence[DeratingPoint]) -> FloatArray:
    """Evaluate the private piecewise-linear fault without a phase shift.

    Parameters
    ----------
    times_s : ndarray
        Elapsed times, including interval midpoints such as 119.5 seconds.
    points : sequence of DeratingPoint
        Strictly increasing validated control points.

    Returns
    -------
    ndarray
        One before the first point, linear between points, last value after
        the final point. Empty points describe a healthy matched run.
    """
    if not points:
        return np.ones_like(times_s, dtype=np.float64)
    return np.interp(
        times_s,
        np.array([point.at_s for point in points], dtype=np.float64),
        np.array([point.multiplier for point in points], dtype=np.float64),
        left=1.0,
        right=points[-1].multiplier,
    )


@dataclass(slots=True)
class ReserveEvaluator:
    """Track continuous endpoint dwell below one private energy reserve.

    Parameters
    ----------
    reserve_soc : float
        Strict threshold; equality clears the below-reserve timer.
    dwell_s : int
        Required uninterrupted elapsed time since the entry endpoint.

    Notes
    -----
    Initial sampling may record entry at tick zero, but never increments a
    dwell counter. Failure remains latched even if energy later recovers.
    """

    reserve_soc: float
    dwell_s: int
    first_entry_tick: int | None = None
    active_entry_tick: int | None = None
    failure_tick: int | None = None

    def evaluate(self, tick: int, soc: float) -> None:
        """Observe an endpoint without influencing its physical state.

        Parameters
        ----------
        tick : int
            Monotonically sampled elapsed simulation seconds.
        soc : float
            Noiseless endpoint stored-energy fraction.
        """
        if soc < self.reserve_soc:
            if self.first_entry_tick is None:
                self.first_entry_tick = tick
            if self.active_entry_tick is None:
                self.active_entry_tick = tick
            if self.failure_tick is None and tick - self.active_entry_tick >= self.dwell_s:
                self.failure_tick = tick
        else:
            self.active_entry_tick = None
