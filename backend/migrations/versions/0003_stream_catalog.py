"""Preserve each stream's measurement catalog across restarts and exports."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Backfill the legacy catalog without rewriting telemetry payloads.

    Notes
    -----
    Existing streams were exclusively ``power-leo.v1``. New streams select
    their immutable catalog when the containing run is created.
    """
    op.add_column(
        "streams",
        sa.Column("catalog_version", sa.String(32), nullable=False, server_default="power-leo.v1"),
        schema="public",
    )


def downgrade() -> None:
    """Remove catalog metadata while leaving immutable frame payloads intact.

    Notes
    -----
    Older application versions cannot interpret spacecraft.v1 frames.
    Downgrading the schema alone does not make those frames compatible.
    """
    op.drop_column("streams", "catalog_version", schema="public")
