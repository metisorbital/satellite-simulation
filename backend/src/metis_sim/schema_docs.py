"""Render database metadata inside documentation builds without opening a database."""

from pathlib import Path
from runpy import run_path

from markdown import Markdown
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor
from sqlalchemy import ColumnDefault, DefaultClause, MetaData
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex

_MARKER = "::: metis-database-schema"


def _cell(value: object) -> str:
    """Escape a value for a Markdown table cell.

    Parameters
    ----------
    value : object
        Value to display.

    Returns
    -------
    str
        Single-line cell content with pipe delimiters escaped.
    """
    return str(value).replace("|", "&#124;").replace("\n", " ")


def _render_schema() -> list[str]:
    """Generate schema Markdown from fresh declarative metadata.

    Returns
    -------
    list of str
        Diagram and schema reference lines for all declared tables.
    """
    # Execute the declarative file afresh: preview rebuilds must not reuse an
    # imported module's cached metadata. This file performs no database I/O.
    source = Path(__file__).parent / "adapters" / "tables.py"
    metadata: MetaData = run_path(str(source))["metadata"]
    dialect = postgresql.dialect()
    tables = sorted(metadata.tables.values(), key=lambda table: table.fullname)
    ids = {table.fullname: f"t{index}" for index, table in enumerate(tables)}
    lines = ["## Relationship Diagram", "", "```mermaid", "flowchart TD"]
    for table in tables:
        lines.append(f'    {ids[table.fullname]}["{table.fullname}"]')
    for table in tables:
        for fk in sorted(table.foreign_key_constraints, key=lambda fk: str(fk.column_keys)):
            parent = fk.referred_table
            label = ", ".join(fk.column_keys)
            lines.append(f'    {ids[table.fullname]} -->|"{label}"| {ids[parent.fullname]}')
    lines += [
        "```",
        "",
        "Arrows point from the referencing table to its parent (declared foreign keys).",
        "They do not imply cascading deletion or enforce consistency between separate foreign keys.",
        "",
        "## Tables and Columns",
        "",
    ]
    for table in tables:
        lines += [
            f"### `{table.fullname}`",
            "",
            table.comment or "",
            "",
            "| Column | PostgreSQL type | Nullable | Keys | Default |",
            "| --- | --- | --- | --- | --- |",
        ]
        for column in table.columns:
            keys = ["PK"] if column.primary_key else []
            keys += [
                f"FK → {fk.target_fullname}"
                for fk in sorted(column.foreign_keys, key=lambda fk: fk.target_fullname)
            ]
            default = "—"
            if isinstance(column.server_default, DefaultClause):
                default = f"server: {column.server_default.arg}"
            elif isinstance(column.default, ColumnDefault):
                default = f"client: {column.default.arg}"
            values = [
                column.name,
                column.type.compile(dialect=dialect),
                "yes" if column.nullable else "no",
                "; ".join(keys) or "—",
                default,
            ]
            lines.append("| " + " | ".join(_cell(value) for value in values) + " |")
        lines += [
            "",
            "PK columns together form the primary key. Client defaults are supplied by SQLAlchemy.",
            "",
        ]
        # Preserve composite keys, checks and FK options through the SQL compiler.
        constraints = sorted(
            str(AddConstraint(constraint).compile(dialect=dialect))
            for constraint in table.constraints
        )
        lines += ["#### Constraints", "", "```sql", *[f"{sql};" for sql in constraints], "```", ""]
        if table.indexes:
            lines += [
                "#### Indexes",
                "",
                "```sql",
                *[
                    f"{CreateIndex(index).compile(dialect=dialect)};"
                    for index in sorted(table.indexes, key=lambda index: index.name or "")
                ],
                "```",
                "",
            ]
    return lines


class _SchemaPreprocessor(Preprocessor):
    """Expand the schema marker before standard Markdown processing."""

    def run(self, lines: list[str]) -> list[str]:
        """Expand the schema directive using current table definitions.

        Parameters
        ----------
        lines : list of str
            Markdown source lines.

        Returns
        -------
        list of str
            Source with generated schema documentation inserted.
        """
        output: list[str] = []
        for line in lines:
            output.extend(_render_schema() if line.strip() == _MARKER else [line])
        return output


class SchemaExtension(Extension):
    """Register database documentation generation in Python-Markdown.

    Notes
    -----
    Used only by the documentation renderer; no live records are read.
    """

    def extendMarkdown(self, md: Markdown) -> None:
        """Register expansion before fenced code and Markdown table processing.

        Parameters
        ----------
        md : Markdown
            Documentation renderer receiving this extension.
        """
        md.preprocessors.register(_SchemaPreprocessor(md), "metis_schema", 35)


def makeExtension(**kwargs: object) -> SchemaExtension:
    """Create the extension through Python-Markdown's discovery interface.

    Parameters
    ----------
    **kwargs : object
        Standard extension configuration options.

    Returns
    -------
    SchemaExtension
        Schema renderer for documentation builds.
    """
    return SchemaExtension(**kwargs)
