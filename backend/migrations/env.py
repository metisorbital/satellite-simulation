"""Explicit migrations for PostgreSQL and isolated SQLite test environments."""

import os

from alembic import context
from metis_sim.adapters.database import Database
from metis_sim.adapters.tables import metadata
from metis_sim.settings import Settings


def run_migrations() -> None:
    """Apply versioned schema changes using the configured deployment URL."""
    settings = Settings.from_env()
    database = Database(os.getenv("METIS_DATABASE_URL", settings.database_url), settings.source_id)
    with database.engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, include_schemas=True)
        with context.begin_transaction():
            context.run_migrations()
    database.close()


run_migrations()
