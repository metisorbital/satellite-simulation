"""Import the pinned SatelliteCOTS corpus with lossless, idempotent verification.

Examples
--------
Prepare and inspect without touching PostgreSQL::

    python -m metis_sim.import_satellitecots --archive telemetry_all.csv.zip --dry-run

Import using the existing environment-selected database::

    python -m metis_sim.import_satellitecots --archive telemetry_all.csv.zip
"""

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from metis_sim.adapters.database import Database
from metis_sim.adapters.observed import decode_chunk_bytes
from metis_sim.adapters.observed_source import (
    CSV_SHA256,
    SATELLITECOTS_DATASET_ID,
    SOURCE_SAMPLE_COUNT,
    prepare_satellitecots,
    verify_prepared,
)
from metis_sim.adapters.tables import observed_datasets, observed_sample_chunks


def _dataset_values(manifest: dict[str, Any]) -> dict[str, Any]:
    names = (
        "dataset_id",
        "title",
        "satellite_id",
        "catalog_version",
        "duration_s",
        "sample_count",
        "columns",
        "archive_sha256",
        "csv_sha256",
        "provenance",
    )
    values = {key: manifest[key] for key in names}
    for key in ("observed_start", "observed_end"):
        values[key] = datetime.fromisoformat(manifest[key])
    return values


def _chunk_values(directory: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    values = {key: value for key, value in manifest.items() if key != "file"}
    for key in ("first_observed_at", "last_observed_at"):
        values[key] = datetime.fromisoformat(values[key])
    values["dataset_id"] = SATELLITECOTS_DATASET_ID
    values["compressed_csv"] = (directory / manifest["file"]).read_bytes()
    return values


def _comparable(value: Any) -> Any:
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def verify_import(connection: Connection, manifest: dict[str, Any]) -> dict[str, Any]:
    """Read every stored chunk and verify exact reconstruction of the source CSV.

    Parameters
    ----------
    connection : Connection
        Transaction-scoped connection to the selected database.
    manifest : dict
        Locally validated preparation metadata and expected chunk boundaries.

    Returns
    -------
    dict
        Verified corpus identity, counts, checksum, and compressed byte size.

    Raises
    ------
    ValueError
        If source identity, metadata, chronology, coverage, or bytes differ.
    """
    dataset = (
        connection.execute(
            select(observed_datasets).where(
                observed_datasets.c.dataset_id == SATELLITECOTS_DATASET_ID
            )
        )
        .mappings()
        .first()
    )
    if dataset is None:
        raise ValueError("SatelliteCOTS is not imported in the selected database")
    for key, expected in _dataset_values(manifest).items():
        if _comparable(dataset[key]) != expected:
            raise ValueError(f"Existing immutable dataset differs at {key}; no overwrite allowed")
    statement = (
        select(observed_sample_chunks)
        .where(observed_sample_chunks.c.dataset_id == SATELLITECOTS_DATASET_ID)
        .order_by(observed_sample_chunks.c.first_sequence)
    )
    rows = connection.execute(statement.execution_options(yield_per=16)).mappings()
    digest = hashlib.sha256(manifest["header"].encode("utf-8"))
    expected_sequence = count = compressed_bytes = 0
    for count, row in enumerate(rows, start=1):
        if count > len(manifest["chunks"]):
            raise ValueError("Stored corpus has extra source chunks")
        expected = manifest["chunks"][count - 1]
        for key, value in expected.items():
            if key == "file":
                continue
            if key in {"first_observed_at", "last_observed_at"}:
                value = datetime.fromisoformat(value)
            if _comparable(row[key]) != value:
                raise ValueError(f"Stored chunk {count - 1} differs at {key}")
        if row["first_sequence"] != expected_sequence:
            raise ValueError("Stored source sample order has a gap or overlap")
        raw = decode_chunk_bytes(row)
        if len(raw.splitlines()) != row["sample_count"]:
            raise ValueError("Stored source chunk has an inconsistent sample count")
        digest.update(raw)
        compressed_bytes += len(row["compressed_csv"])
        expected_sequence += row["sample_count"]
    if (
        count != len(manifest["chunks"])
        or expected_sequence != SOURCE_SAMPLE_COUNT
        or digest.hexdigest() != CSV_SHA256
    ):
        raise ValueError("Stored corpus does not reconstruct the complete original CSV")
    return {
        "dataset_id": SATELLITECOTS_DATASET_ID,
        "sample_count": expected_sequence,
        "chunk_count": count,
        "csv_sha256": digest.hexdigest(),
        "compressed_bytes": compressed_bytes,
        "verified": True,
    }


def import_satellitecots(
    database: Database, directory: Path, manifest: dict[str, Any], *, verify_only: bool = False
) -> dict[str, Any]:
    """Atomically import a complete corpus or verify an identical prior import.

    Parameters
    ----------
    database : Database
        Explicitly selected database. Required tables must already be provisioned;
        this operation never applies or stamps application migrations.
    directory : Path
        Validated local chunk preparation directory.
    manifest : dict
        Manifest returned by ``prepare_satellitecots``.
    verify_only : bool, optional
        Require an existing import and perform readback without data changes.

    Returns
    -------
    dict
        Full readback evidence and whether this invocation inserted the corpus.

    Notes
    -----
    A dataset-specific PostgreSQL advisory transaction lock serializes concurrent
    imports without taking the simulator writer lock. Failure rolls back the
    entire corpus. Existing rows are never updated, replaced, or deleted.
    """
    verify_prepared(directory, manifest)
    with database.engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET LOCAL statement_timeout = '120s'"))
            if not verify_only:
                key = int.from_bytes(
                    hashlib.sha256(SATELLITECOTS_DATASET_ID.encode()).digest()[:8],
                    "big",
                    signed=True,
                )
                acquired = connection.execute(
                    text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}
                ).scalar()
                if not acquired:
                    raise ValueError("Another import currently owns this source dataset")
        existing = connection.execute(
            select(observed_datasets.c.dataset_id).where(
                observed_datasets.c.dataset_id == SATELLITECOTS_DATASET_ID
            )
        ).scalar_one_or_none()
        inserted = existing is None and not verify_only
        if inserted:
            connection.execute(
                observed_datasets.insert(),
                {**_dataset_values(manifest), "imported_at": datetime.now(UTC)},
            )
            for offset in range(0, len(manifest["chunks"]), 32):
                batch = [
                    _chunk_values(directory, chunk)
                    for chunk in manifest["chunks"][offset : offset + 32]
                ]
                connection.execute(observed_sample_chunks.insert(), batch)
        result = verify_import(connection, manifest)
        return {**result, "inserted": inserted}


def main() -> None:
    """Run explicit source preparation, import, or independent verification.

    Notes
    -----
    Database credentials are read from the named environment variable and never
    printed. ``--dry-run`` performs full source validation without connecting.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, required=True, help="Pinned original telemetry_all.csv.zip"
    )
    parser.add_argument(
        "--prepare-dir", type=Path, default=Path(".local/datasets/satellitecots-prepared")
    )
    parser.add_argument("--database-url-env", default="METIS_DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = prepare_satellitecots(args.archive, args.prepare_dir)
    if args.dry_run:
        print(
            json.dumps(
                {key: value for key, value in manifest.items() if key not in {"chunks", "header"}},
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    url = os.getenv(args.database_url_env)
    if not url:
        parser.error(f"Environment variable {args.database_url_env} must select a database")
    database = Database(url, "satellitecots-corpus-import")
    try:
        result = import_satellitecots(
            database, args.prepare_dir, manifest, verify_only=args.verify_only
        )
        print(json.dumps(result, indent=2))
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
