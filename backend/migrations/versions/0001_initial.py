"""Create the frozen version-one public and private persistence schema."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create version-one tables independently of future application metadata."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE SCHEMA IF NOT EXISTS private")
        op.execute("REVOKE ALL ON SCHEMA private FROM PUBLIC")
    op.create_table(
        "configuration_revisions",
        sa.Column("configuration_id", sa.String(length=36), nullable=False),
        sa.Column("canonical_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "configuration",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "resolved",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("configuration_id"),
        schema="private",
    )
    op.create_table(
        "idempotency_records",
        sa.Column("scope", sa.String(length=256), nullable=False),
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "response",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("scope", "key"),
        schema="private",
    )
    op.create_table(
        "runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("configuration_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "public_status",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column(
            "manifest",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.Column("retain", sa.Boolean(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('created','running','paused','completed','stopped','failed','aborted')"
        ),
        sa.ForeignKeyConstraint(
            ["configuration_id"],
            ["private.configuration_revisions.configuration_id"],
        ),
        sa.PrimaryKeyConstraint("run_id"),
        schema="private",
    )
    op.create_index(
        "one_active_run_per_source",
        "runs",
        ["source_id"],
        unique=True,
        schema="private",
        postgresql_where=sa.text("status IN ('running', 'paused')"),
        sqlite_where=sa.text("status IN ('running', 'paused')"),
    )
    op.create_table(
        "truth_records",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("satellite_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["private.runs.run_id"],
        ),
        sa.PrimaryKeyConstraint("run_id", "satellite_id", "sequence"),
        schema="private",
    )
    op.create_table(
        "streams",
        sa.Column("stream_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("satellite_id", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("first_sequence", sa.Integer(), nullable=False),
        sa.Column("last_sequence", sa.Integer(), nullable=False),
        sa.Column("expired", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["private.runs.run_id"],
        ),
        sa.PrimaryKeyConstraint("stream_id"),
        schema="public",
    )
    op.create_index(
        op.f("ix_public_streams_run_id"), "streams", ["run_id"], unique=False, schema="public"
    )
    op.create_table(
        "operational_events",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("stream_id", sa.String(length=36), nullable=False),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.CheckConstraint("event_sequence >= 0 AND event_sequence <= 9007199254740991"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["private.runs.run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["stream_id"],
            ["public.streams.stream_id"],
        ),
        sa.PrimaryKeyConstraint("source_id", "stream_id", "event_sequence"),
        schema="public",
    )
    op.create_index(
        "operational_events_stream_sequence",
        "operational_events",
        ["stream_id", "event_sequence"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "operational_events_stream_time",
        "operational_events",
        ["stream_id", "observed_at"],
        unique=False,
        schema="public",
    )
    op.create_table(
        "telemetry_frames",
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("stream_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("emitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=False,
        ),
        sa.CheckConstraint("sequence >= 0 AND sequence <= 9007199254740991"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["private.runs.run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["stream_id"],
            ["public.streams.stream_id"],
        ),
        sa.PrimaryKeyConstraint("source_id", "stream_id", "sequence"),
        schema="public",
    )
    op.create_index(
        "frames_run_time",
        "telemetry_frames",
        ["run_id", "observed_at"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "telemetry_frames_stream_sequence",
        "telemetry_frames",
        ["stream_id", "sequence"],
        unique=False,
        schema="public",
    )
    op.create_index(
        "telemetry_frames_stream_time",
        "telemetry_frames",
        ["stream_id", "observed_at"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    """Remove only version-one tables when an explicit rollback is requested."""
    op.drop_index("telemetry_frames_stream_time", table_name="telemetry_frames", schema="public")
    op.drop_index(
        "telemetry_frames_stream_sequence", table_name="telemetry_frames", schema="public"
    )
    op.drop_index("frames_run_time", table_name="telemetry_frames", schema="public")
    op.drop_table("telemetry_frames", schema="public")
    op.drop_index(
        "operational_events_stream_time", table_name="operational_events", schema="public"
    )
    op.drop_index(
        "operational_events_stream_sequence", table_name="operational_events", schema="public"
    )
    op.drop_table("operational_events", schema="public")
    op.drop_index(op.f("ix_public_streams_run_id"), table_name="streams", schema="public")
    op.drop_table("streams", schema="public")
    op.drop_table("truth_records", schema="private")
    op.drop_index(
        "one_active_run_per_source",
        table_name="runs",
        schema="private",
        postgresql_where=sa.text("status IN ('running', 'paused')"),
        sqlite_where=sa.text("status IN ('running', 'paused')"),
    )
    op.drop_table("runs", schema="private")
    op.drop_table("idempotency_records", schema="private")
    op.drop_table("configuration_revisions", schema="private")
