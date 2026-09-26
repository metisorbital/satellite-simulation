"""Relational identities and transactional logs; private rows never become API DTOs."""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

metadata = MetaData()
document = JSON().with_variant(JSONB, "postgresql")

configurations = Table(
    "configuration_revisions",
    metadata,
    Column("configuration_id", String(36), primary_key=True),
    Column("canonical_hash", String(64), nullable=False),
    Column("configuration", document, nullable=False),
    Column("resolved", document, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    schema="private",
)
runs = Table(
    "runs",
    metadata,
    Column("run_id", String(36), primary_key=True),
    Column(
        "configuration_id",
        ForeignKey("private.configuration_revisions.configuration_id"),
        nullable=False,
    ),
    Column("source_id", String(64), nullable=False),
    Column("user_id", String(36), nullable=True),
    Column("status", String(16), nullable=False),
    Column("public_status", document, nullable=False),
    Column("manifest", document, nullable=False),
    Column("retain", Boolean, nullable=False, default=False),
    Column("ended_at", DateTime(timezone=True)),
    CheckConstraint(
        "status IN ('created','running','paused','completed','stopped','failed','aborted')"
    ),
    schema="private",
)
Index(
    "one_active_run_per_source",
    runs.c.source_id,
    unique=True,
    postgresql_where=text("status IN ('running', 'paused')"),
    sqlite_where=text("status IN ('running', 'paused')"),
)
streams = Table(
    "streams",
    metadata,
    Column("stream_id", String(36), primary_key=True),
    Column("source_id", String(64), nullable=False),
    Column("satellite_id", String(64), nullable=False),
    Column("run_id", ForeignKey("private.runs.run_id"), nullable=False, index=True),
    Column("first_sequence", Integer, nullable=False, default=0),
    Column("last_sequence", Integer, nullable=False, default=-1),
    Column("expired", Boolean, nullable=False, default=False),
    schema="public",
)


def _public_log(name: str, sequence: str) -> Table:
    return Table(
        name,
        metadata,
        Column("source_id", String(64), primary_key=True),
        Column("stream_id", ForeignKey("public.streams.stream_id"), primary_key=True),
        Column(sequence, Integer, primary_key=True),
        Column("run_id", ForeignKey("private.runs.run_id"), nullable=False),
        Column("observed_at", DateTime(timezone=True), nullable=False),
        Column("emitted_at", DateTime(timezone=True), nullable=False),
        Column("committed_at", DateTime(timezone=True), nullable=False),
        Column("payload_hash", String(64), nullable=False),
        Column("payload", document, nullable=False),
        CheckConstraint(f"{sequence} >= 0 AND {sequence} <= 9007199254740991"),
        schema="public",
    )


frames = _public_log("telemetry_frames", "sequence")
events = _public_log("operational_events", "event_sequence")
for table, sequence in [(frames, "sequence"), (events, "event_sequence")]:
    Index(f"{table.name}_stream_sequence", table.c.stream_id, table.c[sequence])
    Index(f"{table.name}_stream_time", table.c.stream_id, table.c.observed_at)
Index("frames_run_time", frames.c.run_id, frames.c.observed_at)
Index("frames_run_sequence", frames.c.run_id, frames.c.sequence)

truth = Table(
    "truth_records",
    metadata,
    Column("run_id", ForeignKey("private.runs.run_id"), primary_key=True),
    Column("satellite_id", String(64), primary_key=True),
    Column("sequence", Integer, primary_key=True),
    Column("payload_hash", String(64), nullable=False),
    Column("payload", document, nullable=False),
    schema="private",
)
idempotency = Table(
    "idempotency_records",
    metadata,
    Column("scope", String(256), primary_key=True),
    Column("key", String(128), primary_key=True),
    Column("request_hash", String(64), nullable=False),
    Column("response", document, nullable=False),
    schema="private",
)
