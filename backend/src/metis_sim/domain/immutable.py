"""JSON-compatible immutable mappings used by frozen domain contracts."""

from __future__ import annotations

from typing import Never


class FrozenDict(dict):
    """Prevent ordinary mapping mutations while preserving JSON serialization.

    Notes
    -----
    Construction follows ``dict`` and accepts a mapping, iterable of pairs,
    or keyword items. Values must already have been validated as immutable;
    this wrapper prevents mapping updates but does not freeze nested values.
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
