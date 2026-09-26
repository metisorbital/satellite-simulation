"""Bounded database reads of immutable, compressed original observations."""

import csv
import hashlib
import io
import math
import zlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from metis_sim.adapters.database import Database
from metis_sim.adapters.tables import observed_datasets, observed_sample_chunks
from metis_sim.domain.observed import ObservedDataset, ObservedSample

MAX_CHUNK_ROWS = 4096
MAX_CHUNK_BYTES = 4 * 1024 * 1024


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _dataset(row: Any) -> ObservedDataset:
    return ObservedDataset(
        dataset_id=row["dataset_id"],
        title=row["title"],
        satellite_id=row["satellite_id"],
        catalog_version=row["catalog_version"],
        observed_start=_utc(row["observed_start"]),
        observed_end=_utc(row["observed_end"]),
        duration_s=row["duration_s"],
        sample_count=row["sample_count"],
        columns=tuple(row["columns"]),
        provenance=dict(row["provenance"]),
    )


def decode_chunk_bytes(row: Any) -> bytes:
    """Decompress one bounded chunk and verify its original lexical bytes.

    Parameters
    ----------
    row : mapping
        Stored chunk record with byte count, checksum, and zlib payload.

    Returns
    -------
    bytes
        Unmodified source CSV lines, without the corpus header.

    Raises
    ------
    ValueError
        If compressed data, length, or SHA-256 integrity is inconsistent.
    """
    expected = row["raw_size_bytes"]
    if not 1 <= expected <= MAX_CHUNK_BYTES:
        raise ValueError("Observed chunk exceeds the bounded source size")
    decoder = zlib.decompressobj()
    raw = decoder.decompress(row["compressed_csv"], expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError("Observed chunk length or compression is inconsistent")
    if hashlib.sha256(raw).hexdigest() != row["csv_sha256"]:
        raise ValueError("Observed chunk checksum does not match its source")
    return raw


class ObservedRepository:
    """Read source samples independently of run lifecycle and retention.

    Parameters
    ----------
    database : Database
        Existing application connection owner. No writer lock is required for
        reads; immutable corpus ingestion has its own transaction-scoped lock.
    """

    def __init__(self, database: Database) -> None:
        self.db = database
        self._cache: tuple[tuple[str, int, str], tuple[ObservedSample, ...]] | None = None

    def list_datasets(self) -> list[ObservedDataset]:
        """Return imported, transactionally complete source descriptors.

        Returns
        -------
        list of ObservedDataset
            Sources ordered by stable identity, without future measurements.
        """
        with self.db.engine.connect() as connection:
            rows = connection.execute(
                select(observed_datasets).order_by(observed_datasets.c.dataset_id)
            ).mappings()
            return [_dataset(row) for row in rows]

    def get_dataset(self, dataset_id: str) -> ObservedDataset | None:
        """Find an imported source descriptor by its stable identity.

        Parameters
        ----------
        dataset_id : str
            Dataset identity returned by ``list_datasets``.

        Returns
        -------
        ObservedDataset or None
            Metadata if imported; otherwise ``None``.
        """
        with self.db.engine.connect() as connection:
            row = (
                connection.execute(
                    select(observed_datasets).where(observed_datasets.c.dataset_id == dataset_id)
                )
                .mappings()
                .first()
            )
            return _dataset(row) if row is not None else None

    def read_samples(
        self, dataset_id: str, after_sequence: int = -1, limit: int = 1000
    ) -> list[ObservedSample]:
        """Read a bounded original-order page without filling source gaps.

        Parameters
        ----------
        dataset_id : str
            Immutable corpus identity.
        after_sequence : int, optional
            Exclusive source sequence cursor; ``-1`` starts at row zero.
        limit : int, optional
            Maximum returned rows, from one through 4096.

        Returns
        -------
        list of ObservedSample
            Original rows after the cursor. Empty when the source is exhausted
            or unavailable; timestamps and raw reading units are preserved.
        """
        if after_sequence < -1 or not 1 <= limit <= MAX_CHUNK_ROWS:
            raise ValueError("Observed page requires after_sequence >= -1 and limit in 1..4096")
        dataset = self.get_dataset(dataset_id)
        if dataset is None or after_sequence >= dataset.sample_count - 1:
            return []
        start = after_sequence + 1
        chunks = observed_sample_chunks
        result: list[ObservedSample] = []
        with self.db.engine.connect() as connection:
            row = (
                connection.execute(
                    select(chunks)
                    .where(chunks.c.dataset_id == dataset_id, chunks.c.first_sequence <= start)
                    .order_by(chunks.c.first_sequence.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ValueError("Observed source is missing the requested committed chunk")
            while row is not None and len(result) < limit:
                samples = self._decode(row, dataset)
                if not samples[0].sequence <= start <= samples[-1].sequence:
                    raise ValueError("Observed source has an unexpected sample order gap")
                result.extend(sample for sample in samples if sample.sequence >= start)
                if len(result) >= limit:
                    break
                start = row["first_sequence"] + row["sample_count"]
                row = (
                    connection.execute(
                        select(chunks).where(
                            chunks.c.dataset_id == dataset_id, chunks.c.first_sequence == start
                        )
                    )
                    .mappings()
                    .first()
                )
                if row is None and start < dataset.sample_count:
                    raise ValueError("Observed source is missing a committed chunk")
        return result[:limit]

    def sample_at_or_after(self, dataset_id: str, elapsed_s: int) -> ObservedSample | None:
        """Locate the first original observation at or after a source offset.

        Parameters
        ----------
        dataset_id : str
            Immutable corpus identity.
        elapsed_s : int
            Nonnegative original elapsed seconds, including recording gaps.

        Returns
        -------
        ObservedSample or None
            First qualifying source row, or ``None`` beyond the retained corpus.
            A gap snaps forward to a recorded row without manufacturing data.
        """
        if elapsed_s < 0:
            raise ValueError("Observed source elapsed time must be nonnegative")
        dataset = self.get_dataset(dataset_id)
        if dataset is None or elapsed_s > dataset.duration_s:
            return None
        chunks = observed_sample_chunks
        with self.db.engine.connect() as connection:
            row = (
                connection.execute(
                    select(chunks)
                    .where(chunks.c.dataset_id == dataset_id, chunks.c.last_elapsed_s >= elapsed_s)
                    .order_by(chunks.c.last_elapsed_s, chunks.c.first_sequence)
                    .limit(1)
                )
                .mappings()
                .first()
            )
        if row is None:
            raise ValueError("Observed source is missing the requested time boundary")
        return next(
            (sample for sample in self._decode(row, dataset) if sample.elapsed_s >= elapsed_s), None
        )

    def _decode(self, row: Any, dataset: ObservedDataset) -> tuple[ObservedSample, ...]:
        key = (dataset.dataset_id, row["first_sequence"], row["csv_sha256"])
        cached = self._cache
        if cached is not None and cached[0] == key:
            return cached[1]
        raw = decode_chunk_bytes(row)
        parsed = csv.reader(io.StringIO(raw.decode("utf-8"), newline=""))
        samples: list[ObservedSample] = []
        for offset, fields in enumerate(parsed):
            if len(fields) != len(dataset.columns) + 1:
                raise ValueError("Observed row does not match its source columns")
            at = _utc(datetime.fromisoformat(fields[0]))
            values = tuple(float(value) if value else None for value in fields[1:])
            if any(value is not None and not math.isfinite(value) for value in values):
                raise ValueError("Observed source has a nonfinite reading")
            sequence = row["first_sequence"] + offset
            samples.append(
                ObservedSample(
                    sequence=sequence,
                    observed_at=at,
                    elapsed_s=int((at - dataset.observed_start).total_seconds()),
                    readings=values,
                    source_row=sequence + 2,
                )
            )
        if len(samples) != row["sample_count"] or not samples:
            raise ValueError("Observed chunk row count is inconsistent")
        if (
            samples[0].observed_at != _utc(row["first_observed_at"])
            or samples[-1].observed_at != _utc(row["last_observed_at"])
            or samples[0].elapsed_s != row["first_elapsed_s"]
            or samples[-1].elapsed_s != row["last_elapsed_s"]
        ):
            raise ValueError("Observed chunk time boundaries are inconsistent")
        result = tuple(samples)
        self._cache = (key, result)
        return result
