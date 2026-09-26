"""Pinned SatelliteCOTS source validation and lossless bounded chunk preparation."""

import csv
import hashlib
import io
import json
import math
import zlib
from collections import Counter
from datetime import UTC, datetime
from itertools import islice
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from metis_sim.adapters.observed import MAX_CHUNK_BYTES, MAX_CHUNK_ROWS, decode_chunk_bytes
from metis_sim.domain.satellitecots_catalog import SOURCE_COLUMNS

SATELLITECOTS_DATASET_ID = "satellitecots-bupt1-951b41521351"
SOURCE_COMMIT = "951b41521351d535b7c2354916d9c4991602e8c7"
SOURCE_URL = "https://github.com/TiansuanConstellation/MobiCom24-SatelliteCOTS"
SOURCE_PATH = "CommonData-Telemetries/telemetry_all.csv.zip"
ARCHIVE_SHA256 = "5d761d0bb65730cdbdb364f9c8706e9469bbbc6049cc0ed0b22d95ead8d656fa"
CSV_SHA256 = "800787c7ed5cf8687b4c5d83388857323a4c2ed29965067764c0f656eaf340be"
SOURCE_SAMPLE_COUNT = 10_117_299


def _source_identity() -> dict[str, Any]:
    return {
        "dataset_id": SATELLITECOTS_DATASET_ID,
        "title": "BUPT-1 · SatelliteCOTS recorded telemetry",
        "satellite_id": "BUPT-1",
        "catalog_version": "satellitecots.v1",
        "sample_count": SOURCE_SAMPLE_COUNT,
        "columns": list(SOURCE_COLUMNS),
        "archive_sha256": ARCHIVE_SHA256,
        "csv_sha256": CSV_SHA256,
    }


def _source_provenance() -> dict[str, str]:
    return {
        "source_url": SOURCE_URL,
        "source_commit": SOURCE_COMMIT,
        "source_path": SOURCE_PATH,
        "archive_sha256": ARCHIVE_SHA256,
        "csv_sha256": CSV_SHA256,
        "parser_version": "satellitecots.csv.v1",
        "dataset_repository": SOURCE_URL,
        "dataset_revision": SOURCE_COMMIT,
        "dataset_sha256": CSV_SHA256,
        "timestamp_interpretation": "Naive source timestamps interpreted as UTC according to paper section 2.3.",
        "sampling_limits": "Compiled rows usually 1 s, native battery and temperatures 4 s, MPPT 3 s; 403 source gaps are preserved.",
        "data_mapping_version": "satellitecots.v1",
        "paper_url": "https://arxiv.org/html/2401.03435v2",
        "time_interpretation": "Naive CSV timestamps interpreted as UTC; paper section 2.3 states UTC synchronization.",
        "sampling_note": "Compiled rows usually 1 s; native bus/payload current 1 s, MPPT 3 s, battery and surface temperature 4 s. No resampling or interpolation applied.",
        "storage_encoding": "Original CSV lines in independent zlib chunks of at most 4096 rows.",
    }


def _checksum(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def _parse_at(value: str) -> datetime:
    at = datetime.fromisoformat(value)
    if at.tzinfo is not None or at.microsecond or len(value) != 19:
        raise ValueError("Pinned source must contain naive, whole-second timestamps")
    return at.replace(tzinfo=UTC)


def prepare_satellitecots(archive: Path, directory: Path) -> dict[str, Any]:
    """Validate the pinned source and prepare reusable lossless compressed chunks.

    Parameters
    ----------
    archive : Path
        Original ``telemetry_all.csv.zip`` from the pinned upstream revision.
    directory : Path
        Dedicated local preparation directory. A completed manifest is reused
        only after its checksums and every compressed chunk are verified.

    Returns
    -------
    dict
        JSON-serializable manifest, full-corpus statistics, and chunk boundaries.

    Raises
    ------
    ValueError
        If source bytes, columns, numerical values, chronology, or identity do
        not match the pinned corpus. No database is accessed by this function.
    """
    if _checksum(archive) != ARCHIVE_SHA256:
        raise ValueError("SatelliteCOTS archive does not match the pinned SHA-256")
    manifest_path = directory / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        verify_prepared(directory, manifest)
        return manifest
    directory.mkdir(parents=True, exist_ok=True)
    columns = list(SOURCE_COLUMNS)
    minima = [math.inf] * len(columns)
    maxima = [-math.inf] * len(columns)
    nulls = [0] * len(columns)
    zeros = [0] * len(columns)
    steps: Counter[int] = Counter()
    gaps: list[dict[str, Any]] = []
    chunks: list[dict[str, Any]] = []
    row_count = 0
    previous_at: datetime | None = None
    start: datetime | None = None
    end: datetime | None = None
    csv_digest = hashlib.sha256()
    compressed_bytes = 0
    with ZipFile(archive) as zipped:
        if zipped.namelist() != ["telemetry_all.csv"]:
            raise ValueError("Pinned archive must contain only telemetry_all.csv")
        with zipped.open("telemetry_all.csv") as source:
            header = source.readline()
            if next(csv.reader([header.decode("utf-8")])) != ["Time", *columns]:
                raise ValueError("SatelliteCOTS source columns differ from the catalog")
            csv_digest.update(header)
            while lines := list(islice(source, MAX_CHUNK_ROWS)):
                raw = b"".join(lines)
                if len(raw) > MAX_CHUNK_BYTES:
                    raise ValueError("Observed chunk exceeds the bounded source size")
                csv_digest.update(raw)
                first_at: datetime | None = None
                for fields in csv.reader(io.StringIO(raw.decode("utf-8"), newline="")):
                    if len(fields) != len(columns) + 1:
                        raise ValueError(f"Source row {row_count + 2} has unexpected columns")
                    at = _parse_at(fields[0])
                    if start is None:
                        start = at
                    if first_at is None:
                        first_at = at
                    if previous_at is not None:
                        delta = int((at - previous_at).total_seconds())
                        if delta <= 0:
                            raise ValueError("Pinned source timestamps must be strictly increasing")
                        steps[delta] += 1
                        if delta > 1:
                            gaps.append({"after": previous_at.isoformat(), "seconds": delta})
                    for index, lexical in enumerate(fields[1:]):
                        if not lexical:
                            nulls[index] += 1
                            continue
                        value = float(lexical)
                        if not math.isfinite(value):
                            raise ValueError(
                                f"Source row {row_count + 2} contains a nonfinite value"
                            )
                        minima[index] = min(minima[index], value)
                        maxima[index] = max(maxima[index], value)
                        zeros[index] += value == 0
                    previous_at = end = at
                    row_count += 1
                if first_at is None or start is None or end is None:
                    raise ValueError("Observed source chunk is empty")
                payload = zlib.compress(raw, level=6)
                compressed_bytes += len(payload)
                first_sequence = row_count - len(lines)
                filename = f"{first_sequence:010d}.csv.zlib"
                (directory / filename).write_bytes(payload)
                chunks.append(
                    {
                        "first_sequence": first_sequence,
                        "sample_count": len(lines),
                        "first_elapsed_s": int((first_at - start).total_seconds()),
                        "last_elapsed_s": int((end - start).total_seconds()),
                        "first_observed_at": first_at.isoformat(),
                        "last_observed_at": end.isoformat(),
                        "raw_size_bytes": len(raw),
                        "csv_sha256": hashlib.sha256(raw).hexdigest(),
                        "file": filename,
                    }
                )
    if csv_digest.hexdigest() != CSV_SHA256 or row_count != SOURCE_SAMPLE_COUNT:
        raise ValueError("Complete source CSV does not match its pinned identity")
    if start is None or end is None:
        raise ValueError("Observed corpus is empty")
    profile = {
        "rows": row_count,
        "timestamp_precision_s": 1,
        "duplicate_timestamps": 0,
        "backward_timestamps": 0,
        "gap_count": len(gaps),
        "missing_seconds": sum(gap["seconds"] - 1 for gap in gaps),
        "largest_gap_s": max((gap["seconds"] for gap in gaps), default=0),
        "steps": {str(step): count for step, count in sorted(steps.items())},
        "gaps": gaps,
        "null_counts": dict(zip(columns, nulls, strict=True)),
        "zero_counts": dict(zip(columns, zeros, strict=True)),
        "minima": dict(zip(columns, minima, strict=True)),
        "maxima": dict(zip(columns, maxima, strict=True)),
        "compressed_bytes": compressed_bytes,
        "chunk_count": len(chunks),
    }
    manifest = {
        **_source_identity(),
        "observed_start": start.isoformat(),
        "observed_end": end.isoformat(),
        "duration_s": int((end - start).total_seconds()),
        "header": header.decode("utf-8"),
        "chunks": chunks,
        "provenance": {**_source_provenance(), "profile": profile},
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False))
    return manifest


def verify_prepared(directory: Path, manifest: dict[str, Any]) -> None:
    """Verify cached preparation reconstructs the exact pinned original CSV.

    Parameters
    ----------
    directory : Path
        Directory of bounded compressed CSV chunks.
    manifest : dict
        Preparation metadata to verify before any database writes.

    Raises
    ------
    ValueError
        If identity, ordering, paths, checksums, or complete coverage is invalid.
    """
    for key, expected in _source_identity().items():
        if manifest.get(key) != expected:
            raise ValueError(f"Prepared source identity differs from the pinned corpus at {key}")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Prepared source provenance is missing")
    for key, expected in _source_provenance().items():
        if provenance.get(key) != expected:
            raise ValueError(f"Prepared source provenance differs from the pinned corpus at {key}")
    digest = hashlib.sha256(manifest["header"].encode("utf-8"))
    expected_sequence = 0
    observed_start: datetime | None = None
    observed_end: datetime | None = None
    for chunk in manifest["chunks"]:
        expected_file = f"{expected_sequence:010d}.csv.zlib"
        if chunk["first_sequence"] != expected_sequence or chunk["file"] != expected_file:
            raise ValueError("Prepared source chunks must provide contiguous original rows")
        raw = decode_chunk_bytes(
            {**chunk, "compressed_csv": (directory / expected_file).read_bytes()}
        )
        lines = raw.splitlines()
        expected_count = min(MAX_CHUNK_ROWS, SOURCE_SAMPLE_COUNT - expected_sequence)
        if len(lines) != chunk["sample_count"] or len(lines) != expected_count:
            raise ValueError("Prepared source chunk count is inconsistent")
        first_at = _parse_at(lines[0].split(b",", 1)[0].decode("utf-8"))
        last_at = _parse_at(lines[-1].split(b",", 1)[0].decode("utf-8"))
        if observed_start is None:
            observed_start = first_at
        if (
            (observed_end is not None and first_at <= observed_end)
            or last_at < first_at
            or chunk["first_observed_at"] != first_at.isoformat()
            or chunk["last_observed_at"] != last_at.isoformat()
            or chunk["first_elapsed_s"] != int((first_at - observed_start).total_seconds())
            or chunk["last_elapsed_s"] != int((last_at - observed_start).total_seconds())
        ):
            raise ValueError("Prepared source chunk time boundaries do not match original rows")
        observed_end = last_at
        digest.update(raw)
        expected_sequence += chunk["sample_count"]
    if digest.hexdigest() != CSV_SHA256 or expected_sequence != SOURCE_SAMPLE_COUNT:
        raise ValueError("Prepared chunks do not reconstruct the complete pinned CSV")
    if (
        observed_start is None
        or observed_end is None
        or manifest["observed_start"] != observed_start.isoformat()
        or manifest["observed_end"] != observed_end.isoformat()
        or manifest["duration_s"] != int((observed_end - observed_start).total_seconds())
        or len(manifest["chunks"]) != (SOURCE_SAMPLE_COUNT + MAX_CHUNK_ROWS - 1) // MAX_CHUNK_ROWS
    ):
        raise ValueError("Prepared dataset boundaries do not match the original complete corpus")
