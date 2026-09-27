---
title: Operator Investigations and Cases
description: Review committed measurements, preserve evidence, record recommendations and decisions, and track observed outcomes.
content-type: guide
audience: operators and developers
---

# Operator Investigations and Cases

The mission viewer connects **Early warnings**, **Investigations**, **Case history**,
**Mission planning**, and **Shift Log** to the existing simulation and recorded-data
viewer. A named operator owns each case across their runs.
The workflow stores human assessments, recommendations, and decisions.
It can preserve a separately supplied saved model proposal for review, but does
not generate an AI diagnosis, predict a failure from live telemetry, or execute a
recommendation.

## Investigate a Measurement

1. Open **Early warnings** and select a spacecraft.
   The view reports missing, invalid, or saturated readings, valid positive unserved
   power, and safe mode from its latest committed sample. These are current signals,
   not forecasts. No sample means the signal cannot be evaluated.
   A separately labeled **model prediction** can appear only for the saved,
   source-aligned recorded-mission exercise. It links to a durable case and means
   a replay is held for human review; it is neither a measured fault nor future
   ground truth.
1. Review a signal or choose **Report concern** to describe an operator observation.
   The form fixes the spacecraft and available sequence when opened.
   Enter a title, context, and priority, then create the case.
1. In **Investigations**, review the evidence and record an assessment and missing
   information. The server copies the selected public frame from the database;
   the browser cannot supply replacement readings.
1. Record a recommendation, expected effect, and tradeoffs. Approve, reject, or
   revise it with a reason. This records the operator decision only.
1. Use **Capture latest sample** while still on the originating run to preserve
   later evidence. Record an outcome separately: awaiting observation, supported,
   corrected, or inconclusive. An observed outcome requires explanatory notes.
1. Close the case when the review is complete. Closed cases are read-only.
   **Case history** retains the case, its originating run, decision, outcome,
   evidence, and attributed activity.

Changing recommendation text resets its previous decision and outcome.
A revised decision also clears the previous outcome because the recommendation
has changed. Approval never automatically establishes a supported outcome.
Unsaved form edits prompt before navigation; failed saves retain the draft.
A stale revision returns a conflict so the operator can reload before saving again.

For the linked recorded-mission case, approving the unchanged saved proposal
applies its planning interpretation and resumes the same paused replay.
Rejecting resumes the original interpretation.
Editing or revising the saved recommendation remains a recorded operator narrative;
it cannot rewrite recorded telemetry, execute a spacecraft command, or retroactively
change a replay that has already continued.

## Review Unread Workflow Items

The sidebar badge comes from database-backed per-operator read receipts.
`GET /v1/viewer/notifications` returns visible committed warnings for the current
run and the named operator's open cases, with a versioned unread count.
`POST /v1/viewer/notifications/read` records that operator's acknowledgement of
one visible key and version; it does not resolve a warning, change telemetry, or
close a case.

Warnings keep a stable key while their committed condition remains active.
They become unread again only when the condition reappears after clearing or its
material fingerprint changes.
The saved model-prediction warning is active only while its linked case awaits a
decision and the source-aligned replay remains paused at its committed hold.
Open cases become unread when their revision changes and disappear from the
notification list when closed.
Notification case items use the same latest-100-updated owned-case window as the
case list; this does not extend case-history pagination.

## Review Evidence and History

Initial evidence is immutable. A case created before its first committed sample
can have no initial evidence; later captures appear as separate activities.
Each snapshot preserves the public source and stream, sequence, payload hash,
measurement and commit times, catalog, units, values, and quality states.
Private fault scenarios, seeds, evaluation labels, and future health are excluded.

Historical cases remain available when the operator creates another run or signs
in again. A case from another run cannot open that spacecraft in the current
telemetry view or capture evidence from the new run.
The list returns summaries of the latest 100 updated cases. Opening a case loads
its evidence and latest 50 activities with counts and truncation disclosure.
Older records remain stored.
The current interface does not page through those older records.

Every successful case creation, assessment, recommendation, decision, outcome,
and evidence capture also appends an attributed entry to the originating run's
[Shift Log](shift-log.md), in the same transaction.
Idempotent retries cannot duplicate the case activity or handover entry.
The recorded-mission bridge uses a deterministic case identity, so an interrupted
delivery at a committed hold can be reconciled without creating a second model case.
The wildfire demo also appends a labeled modeled image-delivery result to the
linked case activity and Shift Log. An OFF run has no model case, so its result
appears in the Shift Log only. These entries do not approve a recommendation,
close the case, or change its separately recorded observed outcome.
The Shift Log page shows the current operator's current-run draft and submitted
handovers from all operators and runs. Submitting a handover shares its included
case notes; the case itself and its complete workflow remain owner-only in case
history.

## Review Mission Planning

**Mission planning** shows configured operation windows, their relative start and
end times, and the default mode between windows. One-time windows are labeled
against committed simulation time. Orbit repeats identify the declared first
window; the backend resolves recurrence.

Use **Configure operations** to open the existing constellation editor and save
an immutable new run. Active runs must be stopped before replacement.
Recorded telemetry has no synthetic operation schedule.
Resource forecasting, ground contacts, weather, autonomous replanning, and
mission-calibrated risk thresholds are not implemented.

## Use the Private API

All case routes require a named interactive viewer cookie and an allowed origin.
Shared bearer credentials and anonymous demo sessions cannot access cases.
Writes also require `X-CSRF-Token` and `Idempotency-Key`.
Keep the same key and body when retrying an unconfirmed write.
Metis-only approval and dismissal routes do not bypass these protections; decisions
for a saved prediction use the same case endpoints below.

| Method | Route | Body or result |
| --- | --- | --- |
| GET | `/v1/viewer/cases` | Owned historical cases and list bounds |
| GET | `/v1/viewer/cases/{case_id}` | Owned case detail, evidence, and bounded activities |
| GET | `/v1/viewer/notifications` | Current-run warnings and owned open-case unread state |
| POST | `/v1/viewer/notifications/read` | `key` and `version` acknowledgement receipt |
| POST | `/v1/runs/{run_id}/cases` | `satellite_id`, `title`, `summary`, `priority`, optional `sequence` |
| POST | `/v1/viewer/cases/{case_id}/assessment` | `revision`, `assessment`, `missing_information` |
| POST | `/v1/viewer/cases/{case_id}/recommendation` | `revision`, `recommendation`, `expected_effect`, `tradeoffs` |
| POST | `/v1/viewer/cases/{case_id}/decision` | `revision`, `decision`, `reason`, `revised_recommendation` when revised |
| POST | `/v1/viewer/cases/{case_id}/outcome` | `revision`, `outcome`, `outcome_notes`, `close_case` |
| POST | `/v1/viewer/cases/{case_id}/evidence` | `revision`; capture from the session's current originating run |

Mutations return the updated case. A stale revision or closed case returns HTTP
409. Creation requires the session's current owned run; historical narrative
updates require the stored case owner. Captures require both ownership and the
original run to be current.
Responses use the private Pydantic contracts below and generated Dart types.
These records are never added to public telemetry or consumer exports.

Run `uv run metis-sim migrate` before starting an upgraded backend.
Migration `0007_operator_cases` adds private cases and append-only activities.
Cases retain their originating run during abandoned-run pruning; copied evidence
survives telemetry retention. This adds storage growth for retained case history.
The existing demonstration login remains unsuitable as production authentication.

See [operator workflow validation](../validation/operator-workflows.md) for the
executed local API, database, regression, and browser checks.

## Model Reference

::: metis_sim.domain.cases

::: metis_sim.adapters.cases
