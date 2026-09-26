"""Add durable per-operator notification read receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create warning lifecycle state and operator-specific read receipts."""
    op.create_table(
        "operator_notification_state",
        sa.Column("notification_key", sa.String(256), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("private.runs.run_id"), nullable=False),
        sa.Column("satellite_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('warning')"),
        sa.CheckConstraint("version >= 1"),
        schema="private",
    )
    op.create_index(
        "operator_notification_state_run_active",
        "operator_notification_state",
        ["run_id", "active"],
        schema="private",
    )
    op.create_table(
        "operator_notification_receipts",
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("private.users.user_id"), primary_key=True
        ),
        sa.Column("notification_key", sa.String(256), primary_key=True),
        sa.Column("read_version", sa.Integer, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("read_version >= 1"),
        schema="private",
    )
    op.create_index(
        "operator_notification_receipts_user",
        "operator_notification_receipts",
        ["user_id"],
        schema="private",
    )


def downgrade() -> None:
    """Remove notification records during an explicit schema rollback."""
    op.drop_table("operator_notification_receipts", schema="private")
    op.drop_table("operator_notification_state", schema="private")
