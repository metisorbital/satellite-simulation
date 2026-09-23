"""JSON-compatible immutable mappings used by frozen domain contracts."""

from __future__ import annotations

from typing import Never


class FrozenDict(dict):
    """Prevent ordinary mapping mutations while preserving JSON serialization.

    Parameters
    ----------
    value : dict
        Mapping whose values have already been validated as immutable.
    """

    def _immutable(self, *args: object, **kwargs: object) -> Never:
        """Reject mutation rather than return a modified mapping."""
        raise TypeError("contract mappings are immutable")

    def __copy__(self) -> FrozenDict:
        """Return the immutable mapping unchanged."""
        return self

    def __deepcopy__(self, memo: dict[int, object]) -> FrozenDict:
        """Return the mapping whose contract values are already immutable."""
        return self

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable
    __ior__ = _immutable
