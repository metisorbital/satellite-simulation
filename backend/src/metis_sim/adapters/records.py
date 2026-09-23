"""Atomic immutable writes and retry collision detection."""

import hashlib
from datetime import UTC, datetime
from typing import Any

import rfc8785
from sqlalchemy import insert, select, tuple_
from sqlalchemy.engine import Connection
from sqlalchemy.sql.schema import Table

from metis_sim.adapters import tables
from metis_sim.application.errors import ServiceError


def canonical_hash(payload: Any) -> str:
    """Return a SHA-256 digest of RFC 8785 canonical JSON.

    Parameters
    ----------
    payload : JSON-compatible value
        Strictly validated finite input.

    Returns
    -------
    str
        Lowercase hexadecimal content digest.
    """
    return hashlib.sha256(rfc8785.dumps(payload)).hexdigest()


def utc_now() -> datetime:
    """Return a timezone-aware wall timestamp."""
    return datetime.now(UTC)


def append_immutable(connection: Connection, table: Table, rows: list[dict[str, Any]]) -> None:
    """Append a batch, accepting only byte-equivalent identity retries.

    Parameters
    ----------
    connection : Connection
        Caller-owned transaction shared with the committed clock update.
    table : Table
        Immutable log table containing a payload hash.
    rows : list of dict
        Rows whose serialized timestamps are already frozen.
    """
    if not rows:
        return
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    statement = (
        (pg_insert(table) if connection.dialect.name == "postgresql" else sqlite_insert(table))
        .on_conflict_do_nothing()
        .returning(table.c.payload_hash)
    )
    inserted = connection.execute(statement, rows).all()
    # Executemany rowcount is not portable (Psycopg may report -1). RETURNING
    # distinguishes fresh batches; a retry verifies all conflicts in one read.
    if len(inserted) != len(rows):
        columns = list(table.primary_key)
        identities = [tuple(row[column.name] for column in columns) for row in rows]
        persisted = connection.execute(
            select(*columns, table.c.payload_hash).where(tuple_(*columns).in_(identities))
        ).mappings()
        hashes = {
            tuple(row[column.name] for column in columns): row["payload_hash"] for row in persisted
        }
        for row in rows:
            identity = tuple(row[column.name] for column in columns)
            if hashes.get(identity) != row["payload_hash"]:
                raise ServiceError(
                    "identity_collision", "An immutable identity has conflicting content.", 409
                )


def log_rows(run_id: str, payloads: list[dict[str, Any]], sequence: str) -> list[dict[str, Any]]:
    """Project validated envelopes to indexed durable rows."""
    now = utc_now()
    return [
        dict(
            source_id=p["source_id"],
            stream_id=p["stream_id"],
            **{sequence: p[sequence]},
            run_id=run_id,
            observed_at=datetime.fromisoformat(p["observed_at"].replace("Z", "+00:00")),
            emitted_at=datetime.fromisoformat(p["emitted_at"].replace("Z", "+00:00")),
            committed_at=now,
            payload_hash=canonical_hash(p),
            payload=p,
        )
        for p in payloads
    ]


def prior_result(
    connection: Connection, scope: str, key: str, request_hash: str
) -> dict[str, Any] | None:
    """Read a durable idempotent response or reject changed request content."""
    row = (
        connection.execute(
            select(tables.idempotency).where(
                tables.idempotency.c.scope == scope, tables.idempotency.c.key == key
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise ServiceError("idempotency_conflict", "This key was used with different content.")
    return dict(row["response"])


def record_result(
    connection: Connection, scope: str, key: str, request_hash: str, response: dict[str, Any]
) -> None:
    """Persist the acknowledgement in the same transaction as its mutation."""
    connection.execute(
        insert(tables.idempotency).values(
            scope=scope, key=key, request_hash=request_hash, response=response
        )
    )
