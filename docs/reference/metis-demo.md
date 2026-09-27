---
title: Metis Recorded-Mission Review
description: Review one saved, source-aligned model prediction through the durable operator workflow.
content-type: guide
audience: presenters and developers
---

# Metis Recorded-Mission Review

Metis adds one saved planning prediction to a recorded BUPT-1 replay.
It does not create a synthetic spacecraft, replace the replay, or produce a new forecast while the replay is running.

The saved prediction is available only when the selected BUPT-1 recording begins at its recorded mission origin.
The viewer states when another source or start time is selected; ordinary recorded telemetry remains available in that state.

## Review a Prediction

1. Sign in as a named demo operator and select the source-aligned BUPT-1 replay.
2. Choose **Metis OFF** for the original plan or **Metis ON** for preventive review. The setting is saved with the mission. It can be changed before Start, or while paused before the alert; an existing pending decision cannot be bypassed with the switch.
3. Start the existing recorded run with the normal **Start** control.
4. With Metis ON, the writer commits the review tick, pauses the run, and creates one durable operator case with immutable committed evidence.
5. The **Early warnings** workspace shows a critical **model prediction** item and its linked investigation. The alert is a saved forecast for review, not a measured fault.
6. Choose **Review** to inspect the investigation, or **Approve** in the banner to accept the unchanged saved proposal directly. Both paths use the normal revision-checked, attributed case workflow. An edited proposal requires investigation review.
7. An unchanged approved proposal applies only the recorded mission-planning interpretation and resumes the same replay. A rejection resumes the original interpretation. A revised recommendation remains operator narrative and does not alter recorded telemetry or issue a spacecraft command.
8. Record a later observed outcome separately. It may support, correct, or leave the saved prediction inconclusive.

## Present the Wildfire Mission

The scenario represents an uploaded request for a wildfire image before a response briefing.
Recorded BUPT-1 telemetry streams throughout the demonstration; the energy budget, scheduled imaging, and image reception are a separate modeled demo projection.

| Milestone | Mission time | Source UTC, 21 June 2023 |
| --- | --- | --- |
| Mission begins | T0 | 13:05 |
| Metis ON alert and operator review | T+60 | 14:05 |
| Original routine batch | T+70 | 14:15 |
| Wildfire capture | T+90–91.5 | 14:35–14:36:30 |
| Downlink window | T+100–103 | 14:45–14:48 |
| Response briefing | T+120 | 15:05 |
| Approved routine batch begins | T+122 | 15:07 |

With Metis OFF, the original plan captures the image but cannot power the full downlink window. At T+100 the modeled admission gate blocks transmission: no downlink starts and no usable image reaches the ground. The admission gate is a demo assumption evaluated from the saved energy budget; it is not an observed onboard BUPT-1 command or a second Metis alert.
With Metis ON, the alert proposes moving the routine batch from T+70 to T+122 while retaining the capture and downlink windows.
Approving that unchanged recommendation delivers the illustrative image at T+103, 17 minutes before the briefing, enabling the scenario's emergency response.
Turning Metis on alone does not approve a plan or guarantee delivery: rejecting the change retains the original outcome.

The Overview shows the energy chart, an OFF/ON delivery comparison, and task timeline below the globe. After approval, the ON lane shows the rescheduled routine batch, scheduled capture/downlink, transmission progress, and delivered image at T+103. The OFF baseline uses the same committed clock and shows the blocked downlink. Before approval the proposed lane does not claim execution; with Metis disabled it remains inactive. Comparison outcomes are labeled separately from the active demo plan, and neither changes the recorded telemetry.
Before the alert, Missions shows the uploaded request and original schedule; preventive analysis and the shifted plan appear only after the linked case exists.
The exact alert hint comes from the backend's configured `METIS_ALERT_S`, default 3,600 seconds after T0.
The modeled result is persisted and added to the Shift Log and, when present, the linked case's activity.
It never changes the human-recorded observed outcome to supported.

The warning and case use the existing per-operator read receipts, case revisions, idempotency keys, CSRF protection, ownership checks, activity timeline, and Shift Log attribution.
Acknowledging the warning records only that it was viewed; it does not decide the case.

## Data and Authority Boundaries

`backend/src/metis_agent` owns the saved forecast and planning proposal.
It does not import simulator physics, configuration, scenario, private truth, or evaluator data.
The host gives it only the authenticated operator, authorized recorded run, and public replay status.

The case stores the saved forecast origin, proposal, and planning assumptions as private operator narrative beside immutable public replay evidence.
No prediction fields are added to public frames, consumer exports, visual streams, or operational events.
The replay provides source timestamps and measurements; it does not establish the forecast's assumed battery reserve, task execution, image delivery, access geometry, or link capacity.

Approval records a human decision.
It can resume a paused replay but never uploads a command, modifies historical measurements, changes source telemetry, or establishes that the recommendation was correct.

## Persistence and Recovery

Mission snapshots bind the saved decision, selected source-aligned run, and linked case to the named operator in the database.
The model case identity is deterministic, so recovery reconciliation can link a case created immediately before an interruption without creating another case.

The simulator's ordinary recovery policy still aborts active or paused runs after process restart and preserves their committed history.
It does not seamlessly continue a recorded replay or reconstruct uncommitted state.
If interruption occurs at the committed review point, recovery reconciles the durable case link; operators must explicitly start a new replay when they need another run.

## API Surface

All Metis routes require the signed-in, run-scoped viewer session.
State-changing operator work occurs through the existing private case routes, which also require allowed origin, CSRF token, and `Idempotency-Key`.

| Route | Purpose |
| --- | --- |
| `GET /v1/metis/briefing` | Read the saved forecast/proposal and current run's durable mission state or source-alignment availability. |
| `POST /v1/metis/preference` | Persist `{enabled: true/false}` before the decision boundary, with CSRF and an idempotency key. |
| `GET /v1/metis/runs/{run_id}/outcome` | Read `demo_projection` task states, energy margin, and illustrative delivery progress paced by the current session's committed replay. |
| `POST /v1/viewer/cases/{case_id}/recommendation` | Record an operator revision through the normal case contract. |
| `POST /v1/viewer/cases/{case_id}/decision` | Record approval, rejection, or revision and, when applicable, resolve the paused replay. |
| `POST /v1/viewer/cases/{case_id}/outcome` | Record a separate observed outcome. |

The former Metis-only approval, dismissal, rehearsal, and synthetic mission-launch routes reject requests and direct operators to the attached case.

## Limits

- The source alignment is deliberately narrow: one saved BUPT-1 decision origin, not a general live prediction service.
- The forecast is fixed at its saved origin. It does not re-forecast from later replay samples.
- Critical presentation means an operator decision is required for this demonstration. It does not classify a real spacecraft fault or establish operational urgency beyond the configured exercise.
- The recorded replay preserves telemetry provenance. It contains no synthetic orbit, hidden solar derating, battery state-of-charge, replacement `SAT-1`, or fabricated delivery evidence.
- Model accuracy, calibration, warning lead time, and operational benefit require separate evaluation on held-out and ultimately real mission data.
