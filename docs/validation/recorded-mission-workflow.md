---
title: Recorded mission workflow validation
description: Local evidence for the saved BUPT-1 prediction, durable operator review, and Flutter mission interface.
content-type: reference
audience: developers
---

# Recorded mission workflow validation

Validated locally on 27 September 2026 on `feature/metis-twin-demo`.
Hardware: Apple M3 Pro, macOS (`Darwin arm64`). No deployment or push was
performed. No new test files were added.

## Implemented behavior

- Standard **Start run** attaches the mission to the existing BUPT-1 recorded
  run and stream. The saved forecast requires 21 June 2023 at 13:05 UTC.
  Other source positions retain ordinary replay with the mission unavailable.
- Overview has a compact mission summary opening **Missions**. The separate
  Fly mission and Reset rehearsal controls are removed.
- Mission, forecast, proposal, plan, and case link are persisted in
  `private.mission_states`, added by migration `0009_mission_states`.
- A committed +60-minute hold creates one ordinary investigation with public
  measurement evidence, a labelled model recommendation, and Shift Log activity.
  It appears in Early warnings and the existing per-operator unread counters.
- A critical top-right banner opens that investigation. Web Audio is armed by
  Start/Resume; an explicit sound-enable control also handles restored pages.
  The packaged `soundreality-code-red-185448.mp3` plays once per displayed
  notification version at 50% gain, stopping when the banner is dismissed or
  reviewed, the alert disappears, or the page closes. Hardware audibility was
  not independently measured.
- Approval of the unchanged proposal applies its planning schedule and resumes
  the same recorded stream. Rejection retains the original schedule. Custom
  recommendation approval remains narrative and resumes the original schedule.
  Outcome remains `awaiting_observation` until an operator records it separately.

## Wildfire Demo Follow-Up

### Direct Approval and Split Delivery Follow-Up

The banner now offers **Review** and **Approve**. Direct approval submits the
saved proposal identity through the standard case decision API, preserving
revision, ownership, CSRF, idempotency, case activity, and Shift Log checks.
An uncertain request retains its approval body for an idempotent retry; a
confirmed failure stays visible with a Review/retry message.

The OFF/ON panels use backend lane states at the same committed source time.
The original plan now blocks the unsafe downlink before radio activation at
T+100, with zero progress. This replaces the earlier partial-transmission behavior
described in the historical follow-up below. An approved ON plan transmits at
T+100–103 and delivers at T+103. The proposed lane stays inactive or awaiting
approval until the saved plan is accepted; proposed batch timing is hidden until
the alert exists. Labels distinguish active demo and comparison projections.

Live HTTP verification against the isolated QA PostgreSQL database confirmed:

- OFF run `c9a27a20-405b-4a13-845e-12f3d720305e` had no case or review hold,
  captured the illustrative image, and blocked downlink with progress 0.
- ON run `8278d5f7-9670-40e0-84a3-3c52871caf34` held at exactly T+60 and
  resumed the same single BUPT-1 stream after direct approval. The ON lane
  delivered at T+103 while the OFF comparison remained at zero transmission.
- An edited recommendation and a stale case revision each returned 409 without
  approval. Repeating the accepted request with its idempotency key returned the
  same response and produced one decision activity and one demo-result activity.
- The observed case outcome remained `awaiting_observation`.
- PostgreSQL readback confirmed exactly one saved mission result and one Shift
  Log result for each OFF/ON run.
- Browser verification of the release build showed Review and Approve at the
  T+60 hold. Clicking Approve resumed playback and removed the banner. At the
  desktop breakpoint, Overview showed OFF **NO TRANSMISSION** beside ON
  **Delivered +103**, the image, completed task states, and the energy chart.
  The temporary viewport override was reset and the verification run stopped.
- Existing session/security and contract checks passed: **78 total** (43
  session/security, 35 Python/Dart contracts). No test files were added.
- Ruff, format, mypy (81 source files), Flutter analysis, release compilation,
  and strict documentation compilation passed. The release build retains the
  existing Cupertino font warning.

### Earlier Single-Panel Follow-Up

The Overview now includes the energy-margin chart, progressive illustrative photo,
and task timeline below the globe. The mission has a persisted Metis OFF/ON
setting. Before its actual case exists, Missions shows the original schedule and
mission status, with no preventive forecast or recommended shift.

The source-clock hint is T+60, **21 June 2023 at 14:05 UTC**. The unchanged
T+90 capture and T+100 downlink are protected by the approved T+70 → T+122
routine-batch shift. Delivery finishes at T+103, **14:48 UTC**, 17 minutes before
the briefing. These are explicitly modeled demo outcomes alongside unchanged
recorded telemetry.

Follow-up validation used new isolated QA runs at 900× for bounded verification:

- OFF captured the image, crossed its modeled reserve during downlink, and saved
  `missed_delivery`. It never paused for a model case.
- ON held at exactly T+60. Disabling Metis or manually resuming while its case was
  pending returned 409. Approval resumed the same run and stream, saved
  `delivered` at T+103, and retained the human outcome `awaiting_observation`.
- PostgreSQL readback found one labeled demo result per run in Shift Log, and
  exactly one demo-result activity in the approved case.
- Browser checks confirmed OFF persists across reload, ON can be restored, the
  T+60/14:05 hint is shown, the original timeline and photo panel sit beneath the
  globe, and forecast/recommendation details stay absent before the alert. No
  committed energy trace is shown before Start, including after saving the switch.
- Existing operator-session and Python/Dart contract checks: **54 passed**.
  `PATH=/tmp/metis-flutter/bin:$PATH uv run pytest tests/test_dart_contracts.py tests/contracts/test_contracts.py tests/integration/test_operator_sessions.py -q`.
- Ruff, format, mypy (81 source files), Flutter analysis and release build passed.
  No new test files were added.

The first ON validation attempt read the paused run before the post-commit case
link had become visible. Waiting for the linked case resolved that validation
race; the rerun completed approval, delivery, and audit verification.

## Executed checks

- `uv run ruff check backend/src backend/migrations`: passed.
- `uv run ruff format --check backend/src backend/migrations`: passed.
- `uv run mypy backend/src`: passed across 81 source files.
- `flutter analyze --no-pub`: passed.
- `flutter build web --release --no-wasm-dry-run`: passed. The build reported
  an existing missing Cupertino font-family warning.
- `uv run zensical build --strict`: passed.
- Existing service, ownership, security, editing, persistence, pacing, and public
  contract checks: **92 passed, 1 skipped**. Command:

  ```sh
  uv run pytest tests/integration/test_operator_sessions.py tests/integration/test_security.py tests/integration/test_viewer_editing.py tests/integration/test_persistence.py tests/integration/test_service.py tests/integration/test_runner_pacing.py tests/contracts/test_contracts.py -q
  ```

- Generated Dart contract checks: **5 passed**, including actual Dart parsing,
  using `PATH=/tmp/metis-flutter/bin:$PATH uv run pytest tests/test_dart_contracts.py -q`.
- `git diff --check`: passed.

## Database and browser evidence

An isolated local PostgreSQL database received migration 0009 and five copied
archive chunks (20,480 real source rows) covering the mission period. The original
archive and the pre-existing development server were preserved.

Live HTTP checks established:

1. Observed source, one spacecraft `BUPT-1`, source-aligned Start.
2. Exactly one model alert and a paused run at the default mission +3,600 seconds.
3. Direct Resume rejected with `409 case_approval_required` while review is pending.
4. Stable acknowledgement version and no unread reset from polling.
5. Stale case revision rejected; simultaneous approval/rejection produced one
   `200` and one `409`.
6. The same run and stream continued after the accepted decision; observed outcome
   was not automatically marked supported.
7. Editing the case after continuation did not revive a critical model warning.
8. Another operator could not read the case (`404`).

A missing case-link crash window was injected only in that QA database. Restart
reconciliation recovered the exact same deterministic case; the case count stayed
unchanged and the terminal mission was marked `interrupted`. Already-linked
unresolved terminal missions are also included in recovery. Existing run recovery
policy is retained; this does not establish seamless replay continuation after a
backend restart.

The Flutter browser check confirmed the compact summary opens Missions, the
critical banner appears at the top right with separate warning/investigation
badges, and Review opens the linked case with BUPT-1 committed evidence and the
saved recommendation.

The original MP3, its Flutter release asset, and the asset served by the local
preview were byte-identical (513,024 bytes). The preview returned HTTP 200 with
`audio/mpeg` content type. This confirms packaging and delivery, not speaker
audibility.

## Limits

This uses the branch's saved fixed-origin model prediction, not rolling inference
or a live spacecraft connection. Mission energy scaling and task windows remain
planning assumptions. Recorded measurements are unchanged, and approval sends no
spacecraft command. Neither battery SOC nor actual image delivery is established.
Database migration must be applied before starting an upgraded deployment.
