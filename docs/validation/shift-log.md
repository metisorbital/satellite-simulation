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
  states: ownership column only, catalog column only, and both columns.
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

The full Python run passed **205 checks with one Dart-SDK-related skip** in
230.85 seconds. Re-running the Dart contract module with Flutter's SDK on `PATH`
passed all five checks, including the previously skipped check.
Ruff, formatting, mypy (55 source files), deterministic contract generation, and
the strict documentation build passed.
The two existing JavaScript checks and all 18 Flutter checks passed.

## Boundaries

This is a demo operator/run workflow, not production identity management or a
team-wide shift scheduling system. Automatic expiry and anonymous/system controls
are not falsely attributed to an operator. Submission freezes the application
record; it is not a tamper-evident compliance archive.
Existing public telemetry and generated operational events remain separate.
