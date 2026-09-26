"""Add durable private operator cases and append-only workflow activity."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create indexed private case storage independent of terminal telemetry retention.

    Notes
    -----
    Evidence is copied from committed public telemetry into the private case
    row/activity at capture time. Terminal history expiration removes source
    telemetry rows while cases retain their logical run foreign key; abandoned
    run pruning explicitly excludes runs with cases so provenance remains valid.
    """
    document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table(
        "operator_cases",
        sa.Column("case_id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("private.runs.run_id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("private.users.user_id"), nullable=False),
        sa.Column("satellite_id", sa.String(64), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("assessment", sa.Text, nullable=False),
        sa.Column("missing_information", sa.Text, nullable=False),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("expected_effect", sa.Text, nullable=False),
        sa.Column("tradeoffs", sa.Text, nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("decision_reason", sa.Text, nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("outcome_notes", sa.Text, nullable=False),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("evidence", document),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("priority IN ('monitor','review','urgent')"),
        sa.CheckConstraint("status IN ('open','closed')"),
        sa.CheckConstraint("decision IN ('pending','approved','rejected','revised')"),
        sa.CheckConstraint(
            "outcome IN ('awaiting_observation','supported','corrected','inconclusive')"
        ),
        sa.CheckConstraint("revision >= 1"),
        schema="private",
    )
    op.create_index(
        "operator_cases_user_updated",
        "operator_cases",
        ["user_id", "updated_at"],
        schema="private",
    )
    op.create_index(
        "operator_cases_run_satellite",
        "operator_cases",
        ["run_id", "satellite_id"],
        schema="private",
    )
    op.create_table(
        "case_activities",
        sa.Column("activity_id", sa.String(36), primary_key=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("private.operator_cases.case_id"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("private.users.user_id"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("evidence", document),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('created','assessment','recommendation','decision','outcome','evidence')"
        ),
        schema="private",
    )
    op.create_index(
        "case_activities_case_created",
        "case_activities",
        ["case_id", "created_at"],
        schema="private",
    )


def downgrade() -> None:
    """Remove private case history only during an explicit schema rollback."""
    op.drop_table("case_activities", schema="private")
    op.drop_table("operator_cases", schema="private")
