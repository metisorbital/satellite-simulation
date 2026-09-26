"""Immutable source metadata and original observed samples for recorded playback."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ObservedDataset:
    """Describe a complete, verified observed telemetry corpus.

    Parameters
    ----------
    dataset_id : str
        Stable identity of the pinned source and parser version.
    title : str
        Human-readable source title.
    satellite_id : str
        Actual spacecraft identity; payload devices are not spacecraft.
    catalog_version : str
        Public channel catalog used by the source projection.
    observed_start, observed_end : datetime
        Inclusive original source boundaries, interpreted in UTC as disclosed.
    duration_s : int
        Elapsed source seconds between the inclusive boundaries.
    sample_count : int
        Number of original CSV rows, including duplicate timestamps if present.
    columns : tuple of str
        Ordered source reading names, excluding the timestamp column.
    provenance : dict
        Source revision, checksums, interpretation, and measured completeness.
    """

    dataset_id: str
    title: str
    satellite_id: str
    catalog_version: str
    observed_start: datetime
    observed_end: datetime
    duration_s: int
    sample_count: int
    columns: tuple[str, ...]
    provenance: dict[str, Any]


@dataclass(frozen=True)
class ObservedSample:
    """Represent one original source row without interpolation or resampling.

    Parameters
    ----------
    sequence : int
        Dense zero-based index in the immutable corpus.
    observed_at : datetime
        Original timestamp interpreted using the dataset's disclosed timezone.
    elapsed_s : int
        Source seconds since the first recorded row.
    readings : tuple of float or None
        Source units and ordering from ``ObservedDataset.columns``. Empty source
        cells remain unavailable; conversion to public units belongs to projection.
    source_row : int
        One-based original CSV line number, including the header on line one.
    """

    sequence: int
    observed_at: datetime
    elapsed_s: int
    readings: tuple[float | None, ...]
    source_row: int
