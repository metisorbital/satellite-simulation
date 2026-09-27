"""Persist the operator's mission snapshot on its source-aligned run."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create durable, per-run and per-operator mission state."""
    document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "mission_states",
        sa.Column("run_id", sa.String(36), sa.ForeignKey("private.runs.run_id"), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("private.users.user_id"), primary_key=True
        ),
        sa.Column("state", document, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="private",
    )
    op.create_index(
        "mission_states_user_updated",
        "mission_states",
        ["user_id", "updated_at"],
        schema="private",
    )


def downgrade() -> None:
    """Remove mission snapshots during an explicit schema rollback."""
    op.drop_index("mission_states_user_updated", table_name="mission_states", schema="private")
    op.drop_table("mission_states", schema="private")
