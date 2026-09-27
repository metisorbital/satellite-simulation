---
title: Metis Wildfire Demo Validation
description: Evidence that the Metis demo loses the wildfire image with Metis off and delivers it with Metis on, in simulator physics and through the live API.
content-type: reference
audience: engineering
date: 2026-09-27
---

# Metis Wildfire Demo Validation

Recorded on 27 September 2026 on branch `feature/metis-twin-demo`, based on `69578e7`.
- **Hardware:** MacBookPro18,3 (Apple M1 Pro, 10 cores), macOS 26.6.2.
- **Software:** Python 3.12.12 and Flutter 3.47.5.
- **Database:** local PostgreSQL (`METIS_USE_REMOTE=0`).

## Physics reproduces the page model

`uv run python scripts/metis_demo_evidence.py <demo_origin.json>` flew three runs of `configs/metis-wildfire.yaml` in-process:
- ORIGINAL, the original schedule with the batch at +70;
- METIS, the Metis plan with the batch at +122;
- NOBATCH, a no-batch control.

It compared them with the page's integrator under the same truth: BUPT-1 realized solar and a constant 8.1 W essential load. Margins are energy above the protected reserve (50% charge).

| Run | Capture end | Downlink start | Downlink end | Lowest margin | Enters reserve | Skipped by the start guard |
|---|---:|---:|---:|---:|---:|---|
| ORIGINAL | 1.138 Wh | −0.070 Wh | −0.496 Wh | −2.170 Wh at +115 | +99.51 | downlink at +100, 49.63% charge |
| METIS | 5.629 Wh | 4.421 Wh | 2.416 Wh | +0.743 Wh at +115 | never | none |
| NOBATCH | 5.629 Wh | 4.421 Wh | 2.416 Wh | +0.743 Wh at +115 | never | none |

- **Agreement with the page model:** the largest difference is 0.002 Wh. ORIGINAL is compared only up to the downlink start: after that its guard skips the downlink, which the page model does not.
- **Eclipse edges** in the simulator fall at +15.02, +74.93, +109.93 and +169.85 minutes.
- **Checks passed:**
  - ORIGINAL enters the reserve before the +100 downlink;
  - ORIGINAL skips the downlink and nothing else;
  - METIS skips nothing, and its lowest margin is ≥ +0.5 Wh;
  - the no-batch lowest margin is ≥ 0;
  - the simulator stays within 0.1 Wh of the page model.

The planner port (`metis_agent/planner.py`) reproduces the page's choices and margins for all four input sources:

| Input source | Chosen start |
|---|---:|
| Nominal | +106 |
| Repeat last orbit | +102 |
| Median | +103 |
| Cautious | +122 |

## End to end through the live API

A browser-like client (operator login, CSRF and idempotency headers) flew both plans against `metis-sim demo`: briefing, `POST /v1/viewer/mission-run`, resume and outcome polling.

**Alert flow** (second session, as `operator3`):

| Flow | Held at | Alert | Downlink | Image | Lowest margin | Playback +60 to +180 |
|---|---|---|---|---|---:|---:|
| Metis off | none, resumed at once | none | skipped | lost | −2.17 Wh | 62.6 s |
| Metis on, dismissed | +60, paused | pending, then dismissed | skipped | lost | −2.17 Wh | 61.4 s |
| Metis on, approved | +60, paused | pending, then approved; the Metis plan continued from +60 | done | delivered at +103 | +0.74 Wh | 60.5 s |

- Every launch, including the Metis-plan continuation after approval, took about 1.4 s.
- A second dismiss of the same alert returned 409 `alert_not_pending`.
- **Two sessions, one operator:** session A held a Metis alert and session B approved and launched the Metis plan. Before the fix this failed with `503` ("Database is unavailable", a unique-index violation on the one active run). After it, the launch returned 200, stopped A's held run, and logged no database errors.
- The approval window restarts when a watched mission launches, so approval after an earlier rehearsal is not blocked.

**Start at T0, hold at the alert** (third session, as `operator3`, after the runs stopped starting at +60):
- **Launch:** runs are created at T0 in 0.1 to 1.6 s; the viewer starts them.
- **Metis on:** at +10 the outcome reported no alert and a dismiss returned 409 `alert_not_pending`. The runner paused the run by itself at exactly tick 3600 (+60), 30.7 s after the start, and it was still paused at 3600 two seconds later. The outcome then reported the pending alert, raised at +60.
- **Approve:** the Metis-plan run launched paused at tick 3600 and played +60 to +180 in 61.3 s; image delivered at +103, lowest margin +0.74 Wh, alert approved by Operator 3.
- **Dismiss:** returned 200; the resumed run was running at tick 3960 three seconds later.
- **Metis off:** running at tick 359 three seconds after the start.
- The server log had no database errors or tracebacks.
- A headless-browser screenshot showed the held run with the Metis alert, **Approve and uplink**, **Dismiss** and the folded forecast, at the larger Metis text size.

**First session** (single-run flow, before the alert):

**Launch:** 1.4 to 2.1 s from the request to a run paused at +60, using the warmed engine for each plan.

**Playback:** +60 to +180 took 60.9 s (original) and 61.3 s (Metis) at a requested 120×. Effective speed ranged from 99.6× to 120.4×, and each run committed all 10,801 frames.

**Outcome endpoint:**

| Plan | Capture | Batch | Downlink | Image delivered | Downlink start | Enters reserve | Lowest margin |
|---|---|---|---|---|---:|---:|---:|
| Original | done | done | skipped | no | 49.63% charge | +99.52 | −2.17 Wh |
| Metis | done | done | done | +103 | 73.27% charge | never | +0.74 Wh |

These match the in-process evidence.

**Events:** the original run emits `low_energy_limit_entered`, `operation_skipped` (label `downlink`) and `low_energy_limit_cleared`. The Metis run emits only mode changes.

**Private data:** the briefing, `/v1/viewer/configuration`, the snapshot and both outcomes contain none of `realized`, `derating`, `multiplier`, `scenario`, `reserve_soc` or `hidden`. The public `environment_source` names the conditions' source only.

**Errors:**
- flying the Metis plan before approval returns 409 `not_approved`;
- the outcome of a run the operator did not launch returns 404;
- the earlier run's outcome stays readable after the next plan flies, for the comparison line.

## Viewer

Headless Chromium (Playwright) opened the running app at 1440×900 and 390×844.
- **Metis off:** the Overview showed the Metis bar, the batch-drained margin, "Image not delivered" with 49.6% against the 50% limit, and the crossed-out downlink on the timeline.
- **Metis on:** the proposal, the countdown and the forecast charts. After approval, "Delivered at +103, 17 minutes before the +120 briefing" with the credited Camp Fire image, and the Metis-off run as a faded comparison line.
- **Overview:** the data-source line read "Conditions: BUPT-1 solar harvest, 21 June 2023 (scaled)".
- **Layout issues fixed:**
  - marker labels overlapping in narrow charts;
  - "Skipped" colliding with the batch label at phone width;
  - an orbit-preview retry loop after a server restart (it now stops after `409 trajectory_not_prepared`).
- **Console:** no errors after that fix.

The headless browser rendered slowly, and its frames sometimes trailed the committed run by several seconds. The outcome endpoint itself stayed in step with the server. The image's mid-downlink sweep was not captured in a screenshot.

## Static checks

- `ruff check`, `ruff format --check` and `mypy backend/src` pass.
- `scripts/generate_contracts.py` regenerates:
  - `schemas/simulation.v1.schema.json`, with `Operation.min_start_soc` and `run.environment_source`;
  - `schemas/operational_event.v1.schema.json` and `schemas/public-api.v1.schema.json`, with `operation_skipped` and `environment_source`;
  - `schemas/metis-agent.v1.schema.json` and `frontend/lib/api/metis_generated.dart`.
- All `configs/*.yaml` still validate.
- `rg "^(from|import) metis_sim" backend/src/metis_agent` finds no imports.
- `flutter analyze` finds no issues. `flutter build web --release --no-web-resources-cdn` succeeds.

## Limits

- **Remote database:** with `METIS_USE_REMOTE=1` (Render, Frankfurt), commits took about 700 ms per four ticks, and playback ran at about 3.5×. Use the local database for demos.
- **Speed evidence:** 120× is measured here for one spacecraft only. The project's validated capacity tier remains 19.89× for ten.
- **Decision time:** 21 June 12:50 was picked after testing. It illustrates the plan; it is not evidence that the plan generalizes.
- **Image:** illustrative. It is a NASA Earth Observatory Landsat 8 scene of the 2018 Camp Fire, not a product of the simulator.
- **Tests:** none were added, following the team rule. The checks above are commands and scripts.
