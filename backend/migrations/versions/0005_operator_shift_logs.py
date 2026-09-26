"""Add durable operator identities and attributed shift handovers."""

from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Preserve historical owners and create attributable operator handovers.

    Notes
    -----
    Revision 0004 has reconciled the historical duplicate 0003 columns.
    Known demo profiles are frozen here; historical unknown IDs retain explicit
    legacy profiles rather than being reassigned to another operator.
    """
    connection = op.get_bind()
    users = op.create_table(
        "users",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("login", sa.String(128), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        schema="private",
    )
    now = datetime.now(UTC)
    profiles = [
        {
            "user_id": "cb7434cd-7c89-4e04-a510-ab0760b13d64",
            "login": "operator1",
            "display_name": "Operator 1",
        },
        {
            "user_id": "50caf6e8-1192-40e0-a99c-e59b4900d4a1",
            "login": "operator2",
            "display_name": "Operator 2",
        },
        {
            "user_id": "cefd24c1-a4ab-4663-ab69-b12a1bdc6d9f",
            "login": "operator3",
            "display_name": "Operator 3",
        },
    ]
    known = {profile["user_id"] for profile in profiles}
    historical = connection.execute(
        sa.text("SELECT DISTINCT user_id FROM private.runs WHERE user_id IS NOT NULL")
    ).scalars()
    for user_id in historical:
        if user_id not in known:
            profiles.append(
                {
                    "user_id": user_id,
                    "login": f"legacy:{user_id}",
                    "display_name": f"Legacy operator ({user_id})",
                }
            )
    connection.execute(users.insert(), [{**profile, "created_at": now} for profile in profiles])
    op.create_foreign_key(
        "runs_user_id_fkey",
        "runs",
        "users",
        ["user_id"],
        ["user_id"],
        source_schema="private",
        referent_schema="private",
    )
    op.create_index("ix_private_runs_user_id", "runs", ["user_id"], schema="private")
    op.create_table(
        "shift_logs",
        sa.Column("shift_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("private.runs.run_id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("private.users.user_id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('draft', 'submitted')"),
        sa.CheckConstraint(
            "(status = 'draft' AND submitted_at IS NULL) OR "
            "(status = 'submitted' AND submitted_at IS NOT NULL)"
        ),
        schema="private",
    )
    op.create_index("ix_private_shift_logs_user_id", "shift_logs", ["user_id"], schema="private")
    op.create_index("ix_private_shift_logs_run_id", "shift_logs", ["run_id"], schema="private")
    op.create_index(
        "one_draft_shift_per_run_user",
        "shift_logs",
        ["run_id", "user_id"],
        unique=True,
        schema="private",
        postgresql_where=sa.text("status = 'draft'"),
        sqlite_where=sa.text("status = 'draft'"),
    )
    op.create_table(
        "shift_log_entries",
        sa.Column("entry_id", sa.String(36), primary_key=True),
        sa.Column(
            "shift_id", sa.String(36), sa.ForeignKey("private.shift_logs.shift_id"), nullable=False
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("private.users.user_id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column(
            "details", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('note','decision','action','unresolved_issue','event')"),
        schema="private",
    )
    op.create_index(
        "ix_private_shift_log_entries_user_id", "shift_log_entries", ["user_id"], schema="private"
    )
    op.create_index(
        "ix_private_shift_log_entries_shift_id", "shift_log_entries", ["shift_id"], schema="private"
    )


def downgrade() -> None:
    """Remove handover history and the FK while preserving run ownership columns.

    Notes
    -----
    Explicit rollback discards users and operator handovers. Both reconciled
    historical 0003 columns remain present.
    """
    op.drop_table("shift_log_entries", schema="private")
    op.drop_table("shift_logs", schema="private")
    op.drop_index("ix_private_runs_user_id", table_name="runs", schema="private")
    op.drop_constraint("runs_user_id_fkey", "runs", schema="private", type_="foreignkey")
    op.drop_table("users", schema="private")
