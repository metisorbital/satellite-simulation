"""Tick-aligned, half-open operational schedule semantics."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class OperationInterval(Protocol):
    """Structural contract for one nonoverlapping command interval.

    Attributes
    ----------
    start_s, end_s : int
        Inclusive start and exclusive end on integer simulation ticks.
    mode : str
        Public operational mode active throughout the interval.
    """

    start_s: int
    end_s: int

    @property
    def mode(self) -> str:
        """Return the configured public operational mode.

        Returns
        -------
        str
            A validated P0 operating mode.
        """
        ...


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
