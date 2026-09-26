---
title: Operator Shift Log Validation
description: Local schema migration, API, attribution, and viewer verification for operator Shift Log.
content-type: reference
audience: contributors
---

# Operator Shift Log Validation

Validated locally on 26 September 2026, macOS arm64 / Apple M3 Pro,
Python 3.12.12, PostgreSQL 17.6 in a disposable Docker container, and the
repository's Flutter SDK and locked dependencies.
No deployed database was changed.
No new automated test files were added.

## Database and API Evidence

- Applied migrations to a fresh PostgreSQL database and three historical `0003`
  states: ownership column only, catalog column only, and both columns; also
  upgraded the reconciled main-branch `0004` schema.
  All reached `0005`, preserved existing run rows, and retained unknown historical
  operator IDs under explicitly labeled legacy profiles.
- Inspected all ten application tables: column names/nullability, primary keys,
  foreign keys, and index column lists matched SQLAlchemy metadata after normalizing
  PostgreSQL's default `public` schema representation.
- `alembic check` reports existing `public` versus default-schema foreign-key
  representation differences. It is not a clean drift-check gate; direct inspection
  above verified the actual constraints instead. No speculative migration was
  generated to churn those existing constraints.
- Exercised the real HTTP API with isolated SQLite storage: named login, entry
  creation, summary editing, submission, creation of a subsequent draft, automatic
  control attribution, and unchanged retries passed.
- Conflicting retries, forged authors, blank narratives, missing CSRF, edits after
  submission, cross-operator reads, anonymous access, and consumer-only access were
  rejected. Failed controls produced no successful-action entry.
- Confirmed Shift Log contracts remain absent from the public telemetry schema.

## Repeatable Checks

Run from the repository root with an isolated PostgreSQL database:

```bash
uv sync --frozen
METIS_DATABASE_URL="$SHIFT_LOG_TEST_DATABASE_URL" uv run metis-sim migrate
METIS_TEST_DATABASE_URL="$SHIFT_LOG_TEST_DATABASE_URL" uv run pytest -q
uv run ruff check backend/src backend/migrations tests scripts examples
uv run ruff format --check backend/src backend/migrations tests scripts examples
uv run mypy backend/src scripts/generate_contracts.py
uv run python scripts/generate_contracts.py
git diff --exit-code -- schemas frontend/lib/api/generated.dart frontend/lib/api/shift_log_generated.dart
uv run zensical build --clean --strict
npm --prefix frontend ci
npm --prefix frontend test
npm --prefix frontend run prepare:cesium
cd frontend
flutter analyze
flutter test
flutter build web --release --no-web-resources-cdn
```

The final full Python run passed **206 checks** in 141.34 seconds with the Dart SDK
on `PATH` and PostgreSQL gates enabled.
Ruff, formatting, mypy (55 source files), deterministic contract generation, and
the strict documentation build passed.
The two existing JavaScript checks and all 18 Flutter checks passed.
Flutter analysis and the release web build also passed.

## Browser Verification

The final build was served with a fresh migrated PostgreSQL database on an isolated
loopback port. Named operator login, simulation start, automatic action logging,
manual note creation, summary saving, and submission all succeeded.
A database join confirmed both entries in the submitted shift referenced its
registered operator. Closing with unsaved text showed **Keep editing** and
**Discard and close**; explicit logout returned to the login screen.

A separate transaction probe confirmed that a missing author rolls back both the
run update and idempotency acknowledgement. An automatic lease-cleanup stop changed
the run state without adding an entry attributed to a human.

## Boundaries

This is a demo operator/run workflow, not production identity management or a
team-wide shift scheduling system. Automatic expiry and anonymous/system controls
are not falsely attributed to an operator. Submission freezes the application
record; it is not a tamper-evident compliance archive.
Existing public telemetry and generated operational events remain separate.
