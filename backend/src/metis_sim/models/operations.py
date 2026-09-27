"""Tick-aligned, half-open operational schedule semantics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import pi, sqrt
from typing import Protocol

from metis_sim.models.constants import MU_M3_S2


class OperationInterval(Protocol):
    """Structural contract for one nonoverlapping command interval.

    Attributes
    ----------
    start_s, end_s : int
        Inclusive start and exclusive end on integer simulation ticks.
    mode : str
        Public operational mode active throughout the interval.
    """

    @property
    def start_s(self) -> int:
        """Return the inclusive start.

        Returns
        -------
        int
            Elapsed simulated seconds.
        """
        ...

    @property
    def end_s(self) -> int:
        """Return the exclusive end.

        Returns
        -------
        int
            Elapsed simulated seconds.
        """
        ...

    @property
    def mode(self) -> str:
        """Return the configured public operational mode.

        Returns
        -------
        str
            A validated P0 operating mode.
        """
        ...


class ScheduledOperation(OperationInterval, Protocol):
    """Configuration interval with optional nominal-orbit recurrence.

    Attributes
    ----------
    repeat : str or None
        ``orbit`` repeats the interval; ``None`` leaves it one-time.
    """

    @property
    def repeat(self) -> str | None:
        """Return the recurrence policy.

        Returns
        -------
        str or None
            Validated recurrence selection.
        """
        ...

    @property
    def added_load_w(self) -> float:
        """Return the load added while the interval is active.

        Returns
        -------
        float
            Watts added to the mode's profile load.
        """
        ...

    @property
    def label(self) -> str | None:
        """Return the optional public task identifier.

        Returns
        -------
        str or None
            Task label such as ``downlink``.
        """
        ...

    @property
    def min_start_soc(self) -> float | None:
        """Return the onboard start guard.

        Returns
        -------
        float or None
            Minimum state of charge at the window start, or no guard.
        """
        ...


@dataclass(frozen=True, slots=True)
class ResolvedOperation:
    """One immutable, absolute interval after recurrence expansion.

    Attributes
    ----------
    start_s, end_s : int
        Inclusive start and exclusive end in elapsed simulated seconds.
        The end may exceed the run duration for its final partial window.
    mode : str
        Operational mode active throughout the interval.
    added_load_w : float
        Watts added to the mode's profile load during the interval.
    label : str or None
        Optional public task identifier.
    min_start_soc : float or None
        Skip the window when the state of charge at its start is below this.
    """

    start_s: int
    end_s: int
    mode: str
    added_load_w: float = 0.0
    label: str | None = None
    min_start_soc: float | None = None


def resolve_operations(
    operations: Sequence[ScheduledOperation], duration_s: int, semi_major_axis_m: float
) -> tuple[ResolvedOperation, ...]:
    """Expand a validated schedule at a fixed nominal orbital cadence.

    Parameters
    ----------
    operations : sequence of ScheduledOperation
        One-time or orbit-repeating half-open intervals.
    duration_s : int
        Inclusive final simulation tick.
    semi_major_axis_m : float
        Validated initial orbital semi-major axis in metres.

    Returns
    -------
    tuple of ResolvedOperation
        Sorted, nonoverlapping intervals whose starts are within the run.
        Final ends remain untruncated to preserve terminal endpoint mode.

    Raises
    ------
    ValueError
        Any expanded intervals overlap, including repetitions of one task.

    Notes
    -----
    Recurrence uses ``T = 2*pi*sqrt(a**3/mu)`` from the initial orbit, not
    measured J2 crossings. Each offset is independently rounded to the
    nearest integer tick (ties to even); window duration stays unchanged.
    """
    period_s = 2.0 * pi * sqrt(semi_major_axis_m**3 / MU_M3_S2)
    resolved: list[ResolvedOperation] = []
    for operation in operations:
        occurrence = 0
        while (start := operation.start_s + round(occurrence * period_s)) <= duration_s:
            resolved.append(
                ResolvedOperation(
                    start,
                    start + operation.end_s - operation.start_s,
                    operation.mode,
                    operation.added_load_w,
                    operation.label,
                    operation.min_start_soc,
                )
            )
            if operation.repeat is None:
                break
            occurrence += 1
    resolved.sort(key=lambda item: (item.start_s, item.end_s))
    for previous, current in zip(resolved, resolved[1:], strict=False):
        if current.start_s < previous.end_s:
            raise ValueError("operations must not overlap, including orbit repetitions")
    return tuple(resolved)


def operational_mode(tick: int, initial_mode: str, operations: Sequence[OperationInterval]) -> str:
    """Resolve endpoint mode with deterministic [start,end) precedence.

    Parameters
    ----------
    tick : int
        Endpoint elapsed seconds from the common run epoch.
    initial_mode : str
        Mode used outside any explicit command interval.
    operations : sequence of OperationInterval
        Validated nonoverlapping public operations.

    Returns
    -------
    str
        Active mode; operations at tick zero take effect immediately.
    """
    for operation in operations:
        if operation.start_s <= tick < operation.end_s:
            return operation.mode
    return initial_mode


def operational_added_load(tick: int, operations: Sequence[ResolvedOperation]) -> float:
    """Resolve the task load added at an endpoint with [start,end) precedence.

    Parameters
    ----------
    tick : int
        Endpoint elapsed seconds from the common run epoch.
    operations : sequence of ResolvedOperation
        Validated nonoverlapping resolved operations.

    Returns
    -------
    float
        Watts added to the active mode's profile load; zero outside any task.
    """
    for operation in operations:
        if operation.start_s <= tick < operation.end_s:
            return operation.added_load_w
    return 0.0
