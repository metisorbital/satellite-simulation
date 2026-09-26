"""Persist the demo operator identity privately with each new run."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add nullable ownership without changing legacy run records.

    Notes
    -----
    Existing runs remain anonymous; no identity is inferred or backfilled.
    """
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
