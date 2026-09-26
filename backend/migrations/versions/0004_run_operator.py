"""Persist the demo operator identity privately with each new run."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add run ownership and reconcile either historical ``0003`` schema.

    Notes
    -----
    Two independent migrations once shared revision ``0003``. A database
    already stamped with it may have applied either one. Inspect columns so
    both paths converge without rewriting existing records.
    """
    inspector = sa.inspect(op.get_bind())
    stream_columns = {
        column["name"] for column in inspector.get_columns("streams", schema="public")
    }
    if "catalog_version" not in stream_columns:
        op.add_column(
            "streams",
            sa.Column(
                "catalog_version",
                sa.String(32),
                nullable=False,
                server_default="power-leo.v1",
            ),
            schema="public",
        )
    run_columns = {column["name"] for column in inspector.get_columns("runs", schema="private")}
    if "user_id" not in run_columns:
        op.add_column(
            "runs", sa.Column("user_id", sa.String(length=36), nullable=True), schema="private"
        )


def downgrade() -> None:
    """Remove demo ownership while preserving run history.

    Notes
    -----
    Rolling back this feature intentionally discards its operator association.
    """
    op.drop_column("runs", "user_id", schema="private")
