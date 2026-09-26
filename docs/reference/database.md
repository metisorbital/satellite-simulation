---
title: Database Tables and Relationships
description: Model-derived database tables, columns, keys, indexes, and relationships.
content-type: reference
audience: developers
---

# Database Tables and Relationships

This page describes the application schema declared in
`backend/src/metis_sim/adapters/tables.py`.
The diagram, columns, constraints, and indexes below are generated from SQLAlchemy
metadata on every documentation build; they are not a snapshot of a deployed database.
No database connection or stored data is used to build this page.

## How the Data Fits Together

**Users** identify operators. **Shift logs** collect an operator’s handover for a run,
and **shift log entries** record notes, decisions, actions, events, and unresolved issues.
Each entry references one user; one user can author many entries.
See [Operator Shift Log](shift-log.md) for the workflow and identity boundary.

**Operator cases** retain a named operator's investigation, recommendation,
decision, and observed outcome for an originating run. **Case activities** append
the submitted narrative and immutable public evidence snapshots.
See [Operator cases](operator-cases.md) for ownership, retention, and list bounds.

A **configuration revision** stores submitted and resolved configuration.
A **run** executes one revision and records its lifecycle and provenance.
Each run has **streams** identifying its satellites' public measurements.
**Telemetry frames** and **operational events** belong to both a stream and a run.
**Truth records** hold private scenario/evaluation data for a satellite within a run.
**Idempotency records** store retry responses by scope and key, independently of foreign keys.

**Observed datasets** identify immutable imported corpora by pinned upstream
revision and archive/CSV checksums. **Observed sample chunks** retain bounded,
losslessly compressed original CSV rows with indexed sequence and time bounds.
They live in `private`, separately from playback runs and history expiration.
An observed run references the source identity in its manifest and writes only
the frames actually replayed into the existing public telemetry log.
See the [SatelliteCOTS inventory](../research/satellitecots.md) for source scope.

- The `private` schema contains configuration revisions, runs, truth, idempotency records, users, and shift logs with their entries.
- The `public` schema contains stream metadata and durable measurement/event logs.
  The schema name does not grant anonymous API or database access.
  Public API responses use allowlisted projections; they do not expose every database column.
- `source_id` and `satellite_id` are identifiers without separate source or satellite
  tables in this project. `user_id` references the private user directory.
  Satellite definitions live inside configuration JSON; telemetry values live inside payload JSON.
- Frames and events each have separate foreign keys to their run and stream.
  Those constraints alone do not prove that both references describe the same run
  or that the row's `source_id` matches its stream.
- A parent can have zero or more child rows under the current constraints.
  Foreign keys do not declare cascading deletes.
- Alembic's version bookkeeping is not an application model and is not listed below.

See [data contracts](../contracts.md) for JSON payload meanings and privacy rules,
[public data models](public-data.md) for generated Python field documentation,
and [persistence interfaces](persistence.md) for read/write behavior.

Revision `0004` reconciles historical duplicate `0003` schemas; revision `0005`
adds users and Shift Log tables while preserving historical run ownership.
This model reference does not inspect a deployed database.
Revision `0006` adds observed source storage and immutable-row guards.
It can adopt matching preprovisioned tables without changing their data.

::: metis-database-schema

## Keep This Reference Current

Run the normal documentation commands from the repository root:

```bash
uv sync --frozen
uv run zensical build --clean --strict
uv run zensical serve
```

Open **Database Tables** in the documentation navigation.
The preview watches `tables.py`; changing the model rebuilds the reference.
The existing documentation CI workflow also builds it for pull requests and main-branch pushes.
Publishing still follows that workflow's `PUBLISH_DOCS` setting.

The local `metis_sim.schema_docs` Markdown extension expands this page's directive
from fresh metadata, including new tables and foreign keys.
It uses the existing SQLAlchemy and [Python-Markdown extension API](https://python-markdown.github.io/extensions/api/);
no extra schema documentation library is required.
Edit model declarations and migrations together when changing storage.
The explanatory text above describes application behavior and still requires review
when that behavior changes; structured schema details are generated automatically.
