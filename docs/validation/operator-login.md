---
title: Mock Operator Login Validation
description: Local verification of Flutter demo identities, session lifecycle, and private database ownership.
content-type: reference
audience: maintainers
---

# Mock Operator Login Validation

The September 26, 2026 change adds a Flutter login gate for `operator1`, `operator2`,
and `operator3`. Stable UUIDs are packaged in `backend/src/metis_sim/data/mock_operators.json`.
Any nonempty demo password is accepted without verification or persistence.
The backend chooses the identity, stores `private.runs.user_id`, and preserves it
when editing or resetting a mission. Passwords and operator IDs do not enter telemetry.

The development login in Research Copilot's `app/chat_app.py`, `app/auth_helper.py`,
and `api/auth/auth_client.py` informed the stable mock identity and logout pattern.
A separate Terra agent at medium effort inspected that local implementation.
This implementation uses the existing signed, HttpOnly viewer cookie and CSRF boundary.

## Executed Checks

Verification used an Apple M3 Pro with 18 GB RAM, macOS arm64, Python 3.12.12,
PostgreSQL 17.6 in a dedicated local container, and Flutter 3.47.5 / Dart 3.13.4
from the cached `metis-frontend-check` container. Application, migration, and test
databases were separate. No production database was used.

| Check | Result |
|---|---|
| `METIS_TEST_DATABASE_URL=… uv run pytest -q` | 204 passed, 1 skipped in 148.55 seconds; PostgreSQL coverage enabled. |
| Operator and generated-contract tests with `DART_EXECUTABLE` pointing to the pinned container | 24 passed, including the separately rerun Dart test skipped above. |
| `flutter analyze --no-pub` | No issues. |
| `flutter test --no-pub` | 18 passed. |
| `flutter build web --no-pub --release --no-web-resources-cdn` | Final build passed in 36.7 seconds. |
| `npm --prefix frontend test` | Both Cesium interpolation/resynchronization tests passed; numerical tolerances unchanged. |
| Ruff lint and formatting | Passed; 69 Python files formatted. |
| mypy | Passed across 40 source files. |
| `uv run zensical build --clean --strict` | Passed. |
| PostgreSQL migration `0002 → 0003 → 0002 → 0003` | Existing legacy row preserved, nullable ownership verified, no inferred user backfill. |
| Wheel packaging | Mock JSON included with exactly three operators and no password fields. |
| Operator browser regression tests | Both cases passed across three repetitions, including exact keyboard-submitted login/password values. |
| `npm --prefix frontend run test:e2e` | Final complete browser suite: 6 passed in 41.7 seconds. |
| Live Flutter and PostgreSQL flow | Login, start, advancing telemetry, pause, stop, reset, logout, second operator login/start/logout passed with zero page errors. |
| Independent database readback | First and second operator runs had distinct expected user IDs and `stopped` status; the reset run retained the first operator's user ID and `created` status. |

The Flutter tests cover the initial gate, login errors, keyboard submission,
logout retry, CSRF rotation, independent operator state, disposed requests,
changed identities on reconnect, and stale unauthorized responses.
Backend tests cover operator isolation, Origin/CSRF checks, private ownership,
reset/edit persistence, signed expiry, stale cookies, and deployment mode boundaries.
Desktop and 390-pixel-wide login screenshots were inspected, along with the live
mission view showing the current operator and logout control. Local evidence is
in `frontend/artifacts/operator-login-desktop.png`, `operator-login-mobile.png`,
and `operator-mission-live.png`; those runtime artifacts are ignored by Git.

## Review Findings Addressed

An independent review identified an expired paused session retaining the single
active-run slot. Mock-owned runs now persist a private lease deadline; a subsequent
login stops expired operator-owned active runs through the normal owner-checked
stop path. Unexpired and legacy runs remain untouched. Tests verify both behaviors.
Cookie `Max-Age` uses the remaining durable lease, including idempotent reset retries.
The independent Flutter review found no remaining lifecycle issue; additional
reconnect regressions verify that another tab's identity cannot silently replace
the operator shown in the current workspace.

## Limits

This is a mock identity demo, not verification of a real person's identity.
The existing single-active-run limit still applies. Logout ends only the departing
operator's active run and keeps its database history under existing retention rules.
No numerical model changes or new performance claims are part of this change.
These results describe local validation; remote CI and production rollout must
be assessed separately.
