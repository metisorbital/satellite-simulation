"""Index the committed run/sequence window used by snapshots and visual streams."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Bound snapshot scans by run identity and the requested sequence window."""
    op.create_index(
        "frames_run_sequence", "telemetry_frames", ["run_id", "sequence"], schema="public"
    )


def downgrade() -> None:
    """Remove the optional read index without touching durable telemetry."""
    op.drop_index("frames_run_sequence", table_name="telemetry_frames", schema="public")
