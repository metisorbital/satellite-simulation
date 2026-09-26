---
title: Operator Workflow Validation
description: Local evidence for private cases, committed telemetry captures, planning, and full-page handover.
content-type: reference
audience: engineering and operators
date: 2026-09-26
---

# Operator Workflow Validation

This change extends the existing Flutter viewer with operator investigations,
recommendations, decisions, observed outcomes, case history, configured planning,
and full-page Shift Log. The [workflow guide](../reference/operator-cases.md)
defines the delivered behavior and limits.

Implementation and verification used a separate `codex/mission-workflows`
worktree based on main `9ea14f9`, with the concurrent operator-switch update
`2e9bb90` integrated before the final PR update. The original checkout and its
concurrent edits were preserved. No source files were removed, and no tests were
written or changed.

## Executed Checks

Local hardware: Apple M3 Pro, arm64, macOS 26.6.2. Tooling: repository-pinned
Python environment, Flutter 3.47.5, and PostgreSQL in the existing local simulator
container. Fresh, dedicated databases separated migration/API checks from the
regression suite and from existing application data.

| Check | Measured result |
| --- | --- |
| `uv run metis-sim migrate` on a fresh dedicated PostgreSQL database | Schema current through additive migration `0007` |
| `METIS_TEST_DATABASE_URL=… uv run pytest -q` | 205 passed, 1 skipped in 190.07 s; PostgreSQL gates enabled |
| `PATH=<flutter>/bin:$PATH uv run pytest -q tests/test_dart_contracts.py` | 5 passed; includes the Dart-runtime check skipped above because the SDK was initially absent from PATH |
| `uv run ruff check backend/src backend/migrations tests scripts examples` | Passed |
| `uv run ruff format --check backend/src backend/migrations tests scripts examples` | 101 files already formatted |
| `uv run mypy backend/src scripts/generate_contracts.py` | No issues in 67 source files |
| Generate contracts and compare bytes before/after | All JSON schemas and generated Dart contracts reproduced without drift |
| `dart format --output=none --set-exit-if-changed lib test` and `flutter analyze` before integrating `2e9bb90` | Passed |
| `flutter test` before integrating `2e9bb90` | 18 passed |
| `npm --prefix frontend test` | 2 passed, including committed-position interpolation |
| `npm --prefix frontend run test:e2e` before integrating `2e9bb90` | 6 existing compiled-browser tests passed in 2.3 min |
| `flutter build web --release --no-web-resources-cdn` | Release build succeeded with local renderer/assets |
| `uv run zensical build --strict` | Passed |
| `git diff --check` | Passed |

The Flutter build retains its existing optional Cupertino font-family warning;
the application uses Material icons and the resulting screens rendered correctly.
Python warnings came from test-adapter deprecations and deliberately unsupported
future-epoch numerical fixtures.

### Concurrent Main Integration

Main's `2e9bb90` replaces the login form with an automatically opened default
operator and sidebar switching. The integrated switch checks unsaved case and
Shift Log edits before ending the session, and rejects duplicate/current-operator
switch requests. Application-only analysis (`flutter analyze lib`) passed and
the existing playback suite passed all 10 checks after integration. The release
web build passed again, and all four existing mission/editor/lifecycle browser
checks passed in 1.1 minutes. The strict documentation build also passed.

Full `flutter analyze` now reports six errors in the unchanged
`test/operator_session_test.dart`: it still calls removed `login`/`logout`
methods and the former builder callback. The two existing operator browser
checks also still target the removed login form. These are inherited from main;
[main's own Simulation gates run](https://github.com/metisorbital/satellite-simulation/actions/runs/36261660449)
fails at analysis for this update. The tests are preserved under the instruction
not to write tests. Full CI cannot be claimed green until these existing checks
are adapted to main's operator-switch behavior.

## Live PostgreSQL and HTTP Verification

An isolated service at loopback port 8898 used three spacecraft, one-second
physics-backed telemetry, a 600-second run, and a declared payload window at
T+120–180 seconds. An inline HTTP rehearsal verified:

- A pre-start case has nullable evidence; a requested unavailable sequence is
  rejected. After starting, an exact committed sequence and later captures retain
  their public values, quality, catalog, hash, and timestamp provenance.
- List responses contain lightweight summaries; owned detail responses contain
  evidence and bounded activities. Other operators cannot list or open the case.
- Missing CSRF is rejected. Stale revisions and mutations of closed cases return
  conflicts. Exact idempotent retries return the original result without duplicate
  activities or handover entries.
- A decision requires a recommendation. Revised text clears the previous outcome.
  Approval and observed outcome are independent.
- Every successful case action has one corresponding Shift Log entry in the
  same transaction. Long narratives are explicitly abbreviated to 4,000 characters
  for handover while full case activity remains stored.
- Historical cases survive a new login/run; evidence cannot be captured from a
  different current run. Private case IDs and text are absent from public snapshots.
- OpenAPI exposes the request models and named-cookie security boundary.

The live rehearsal caught a strict Python/JSON validation mismatch when reading
stored frames. Evidence capture now uses strict JSON-mode `MeasurementFrame`
validation; the public contract was not relaxed. The complete HTTP rehearsal
passed after this repair.

## Browser Rehearsal

The real compiled app was checked against that PostgreSQL service, independently
of the browser suite's mocked API fixtures. Overview retained the rendered Earth,
spacecraft selection, start, 20× speed, pause, and committed measurements.
Telemetry opened and entered/exited full-view focus.

The operator created an eclipse-observation case at committed sequence 456,
saved an assessment and recommendation, approved it with a reason, and recorded
an inconclusive outcome. Navigation prompted for unsaved assessment text.
Reload restored the same durable case, decision, and outcome. Raw evidence is
collapsed by default with count/quality summaries; missing channels are grouped
and are not labeled as diagnosed failures.

Case actions appeared in Shift Log. The operator saved a handover summary and
submitted it; the page showed one submitted, read-only record. Its navigation
guard also preserved unsaved summary text. Planning showed the actual declared
payload window and the configured mode between windows.
Desktop and 390 × 844 layouts were visually inspected.

After integrating main's sidebar switching, an unsaved assessment prevented an
operator switch; keeping the edit retained the original workspace. Switching
after cancelling that temporary draft opened operator2 without operator1's
cases. Switching back retained operator1's original case and immutable evidence
under its historical run. A fresh simulation still started, streamed committed
measurements, and paused. The grouped-warning layout remained readable at
390 × 844.

The final navigation pass verified that current warnings keep their telemetry
shortcut available when older cases exist, selecting a warning's case opens its
investigation, and creating a warning case opens the newly persisted record.
The final compiled browser reported no JavaScript errors.

## Independent Review and Limits

Terra and Luna workers implemented separate modules and reviewed interfaces
outside their own implementation. Review fixes covered owner/session isolation,
closed-case immutability, recommendation/outcome invalidation, bounded list/detail
reads, atomic Shift Log integration, stale-response handling, navigation guards,
draft preservation during reload, and unchanged retries after uncertain writes.
Integration owned the live API and browser verification.

This is a local implementation result, not deployment or flight-validation
evidence. Automated anomaly models, forecasts, generated recommendations, target
planning, weather, and command execution remain outside the delivered workflow.
Case lists return the latest 100 records and detail the latest 50 activities;
older rows are retained but not paginated in this UI. Demo login remains mock
authentication. Remote CI and deployment status must be read separately from
the pull request and running environment.
