"""Add immutable observed corpora independent of execution and retention."""

import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _normalized_check(value: str) -> str:
    value = re.sub(
        r"(\w+)\s+BETWEEN\s+(\d+)\s+AND\s+(\d+)",
        r"\1 >= \2 AND \1 <= \3",
        value,
        flags=re.IGNORECASE,
    )
    return "".join(
        character
        for character in value.lower()
        if not character.isspace() and character not in '()"'
    )


def _validate_table(table: sa.Table) -> None:
    """Reject incompatible prior provisioning rather than silently adopting it."""
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    actual = {
        column["name"]: column for column in inspector.get_columns(table.name, schema="private")
    }
    if set(actual) != set(table.c.keys()):
        raise ValueError(f"Existing private.{table.name} columns differ from revision 0006")
    for column in table.c:
        reflected = actual[column.name]
        expected_type = str(column.type.compile(dialect=connection.dialect))
        actual_type = str(reflected["type"].compile(dialect=connection.dialect))
        if expected_type != actual_type or column.nullable != reflected["nullable"]:
            raise ValueError(
                f"Existing private.{table.name}.{column.name} differs from revision 0006"
            )
    actual_pk = inspector.get_pk_constraint(table.name, schema="private")["constrained_columns"]
    if actual_pk != [column.name for column in table.primary_key.columns]:
        raise ValueError(f"Existing private.{table.name} primary key differs from revision 0006")
    expected_checks = {
        _normalized_check(str(check.sqltext))
        for check in table.constraints
        if isinstance(check, sa.CheckConstraint)
    }
    actual_checks = {
        _normalized_check(check["sqltext"])
        for check in inspector.get_check_constraints(table.name, schema="private")
    }
    if actual_checks != expected_checks:
        raise ValueError(f"Existing private.{table.name} checks differ from revision 0006")
    expected_fks = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
        )
        for constraint in table.foreign_key_constraints
    }
    actual_fks = {
        (
            tuple(fk["constrained_columns"]),
            tuple(
                f"{fk['referred_schema']}.{fk['referred_table']}.{column}"
                for column in fk["referred_columns"]
            ),
        )
        for fk in inspector.get_foreign_keys(table.name, schema="private")
    }
    if actual_fks != expected_fks:
        raise ValueError(f"Existing private.{table.name} foreign keys differ from revision 0006")


def upgrade() -> None:
    """Create compact source storage and its indexed playback boundaries.

    Notes
    -----
    Compressed chunks retain at most 4096 original rows. PostgreSQL guards
    committed source records against UPDATE and DELETE; importing a revision
    allocates a new dataset identity instead of editing an existing corpus.
    """
    document = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    datasets = op.create_table(
        "observed_datasets",
        sa.Column("dataset_id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("satellite_id", sa.String(64), nullable=False),
        sa.Column("catalog_version", sa.String(32), nullable=False),
        sa.Column("observed_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_s", sa.Integer, nullable=False),
        sa.Column("sample_count", sa.Integer, nullable=False),
        sa.Column("columns", document, nullable=False),
        sa.Column("archive_sha256", sa.String(64), nullable=False),
        sa.Column("csv_sha256", sa.String(64), nullable=False),
        sa.Column("provenance", document, nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("sample_count > 0 AND duration_s >= 0"),
        sa.CheckConstraint("observed_end >= observed_start"),
        schema="private",
        if_not_exists=True,
    )
    chunks = op.create_table(
        "observed_sample_chunks",
        sa.Column(
            "dataset_id",
            sa.String(64),
            sa.ForeignKey("private.observed_datasets.dataset_id"),
            primary_key=True,
        ),
        sa.Column("first_sequence", sa.Integer, primary_key=True),
        sa.Column("sample_count", sa.Integer, nullable=False),
        sa.Column("first_elapsed_s", sa.Integer, nullable=False),
        sa.Column("last_elapsed_s", sa.Integer, nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_size_bytes", sa.Integer, nullable=False),
        sa.Column("csv_sha256", sa.String(64), nullable=False),
        sa.Column("compressed_csv", sa.LargeBinary, nullable=False),
        sa.CheckConstraint("first_sequence >= 0 AND sample_count BETWEEN 1 AND 4096"),
        sa.CheckConstraint("first_elapsed_s >= 0 AND last_elapsed_s >= first_elapsed_s"),
        sa.CheckConstraint("last_observed_at >= first_observed_at"),
        sa.CheckConstraint("raw_size_bytes BETWEEN 1 AND 4194304"),
        schema="private",
        if_not_exists=True,
    )
    _validate_table(datasets)
    _validate_table(chunks)
    expected_indexes = {
        "observed_chunks_elapsed": ["dataset_id", "last_elapsed_s", "first_sequence"],
        "observed_chunks_time": ["dataset_id", "last_observed_at", "first_sequence"],
    }
    for name, columns in expected_indexes.items():
        op.create_index(
            name, "observed_sample_chunks", columns, schema="private", if_not_exists=True
        )
    actual_indexes = {
        index["name"]: index
        for index in sa.inspect(op.get_bind()).get_indexes(
            "observed_sample_chunks", schema="private"
        )
    }
    for name, columns in expected_indexes.items():
        index = actual_indexes.get(name)
        if index is None or index["column_names"] != columns or index["unique"]:
            raise ValueError(f"Existing observed index {name} differs from revision 0006")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
            CREATE OR REPLACE FUNCTION private.reject_observed_mutation() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN
                RAISE EXCEPTION 'Observed source corpora are immutable; import a new dataset revision';
            END $$
        """)
        for table in ("observed_datasets", "observed_sample_chunks"):
            trigger = (
                op.get_bind()
                .execute(
                    sa.text("""
                    SELECT tr.tgtype, proc.proname, namespace.nspname
                    FROM pg_trigger AS tr
                    JOIN pg_proc AS proc ON proc.oid = tr.tgfoid
                    JOIN pg_namespace AS namespace ON namespace.oid = proc.pronamespace
                    WHERE tr.tgrelid = to_regclass(:table) AND tr.tgname = :name
            """),
                    {"table": f"private.{table}", "name": f"{table}_immutable"},
                )
                .mappings()
                .first()
            )
            if trigger is None:
                op.execute(f"""
                    CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE
                    ON private.{table} FOR EACH ROW
                    EXECUTE FUNCTION private.reject_observed_mutation()
                """)
            elif tuple(trigger.values()) != (27, "reject_observed_mutation", "private"):
                raise ValueError(f"Existing {table} immutable trigger differs from revision 0006")


def downgrade() -> None:
    """Remove source storage only as an explicit schema rollback.

    Notes
    -----
    Dropping these tables discards the imported source corpus, not run history.
    """
    op.drop_table("observed_sample_chunks", schema="private")
    op.drop_table("observed_datasets", schema="private")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION private.reject_observed_mutation()")
