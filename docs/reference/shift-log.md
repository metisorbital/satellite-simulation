---
title: Operator Shift Log
description: Record operator notes, decisions, actions, unresolved issues, and submitted handovers with durable user attribution.
content-type: guide
audience: operators and developers
---

# Operator Shift Log

The HQ product scope describes a shift record that collects events, notes,
decisions, actions, and unresolved issues, then lets the operator edit and submit
it with a record of who did what.
This implementation provides that workflow for a named demo operator's run.
It records decisions and reported actions; it does not execute real spacecraft commands
or establish that an approved recommendation was correct.

## Record and Submit a Shift

1. Sign in as a named demo operator and open **Shift Log** in the mission viewer.
   The full-page workspace places the retained timeline beside the entry and
   handover composers, stacking them on narrow screens.
2. Add a note, decision, reported action, unresolved issue, or event.
   Successful simulator controls and [case workflow changes](operator-cases.md)
   also create entries automatically.
3. Review the entries and edit the draft's handover summary.
4. Submit the shift when the handover is ready.
   Submitted records remain unchanged; the next entry or simulator control opens a new draft.

Entries preserve the author and server-recorded time.
Corrections should be added as new entries so the original record remains available.
The summary is editable until submission.
Navigation checks for unsaved text and unconfirmed writes.
Submitted handovers are read from the database and visible to every named
operator connected to this application's database, including across different
runs and producer revisions after deployment. A producer source ID is not a
workspace or tenant boundary.
Drafts remain private to their owner and current run. Submission shares the
complete summary and entries, including any automatically recorded case notes.
Other operators cannot edit or submit your draft; submitted records are read-only
for everyone. Reload the Shift Log to read newly submitted handovers.

## Understand User Attribution

`private.users` stores stable operator identities.
`private.runs.user_id` references its owner, while each shift and entry references
its own user through a foreign key.
One user can have many runs, shifts, and entries; each authored entry has exactly one user.
The run owner and the author of an action are separate concepts.
See the [generated database reference](database.md) for current columns and relationships.

The backend takes the entry author from the verified session, never a submitted `user_id`.
The existing mock login directory provisions user profiles at startup.
This feature does not turn the demonstration login into production authentication.
Legacy anonymous runs remain nullable, and anonymous/system controls are not assigned
an invented human author.
Shared deployment bearer credentials do not establish a named operator for Shift Log access.

Successful `start`, `pause`, `resume`, `set_speed`, and `stop` controls from a named
session are recorded in the same database transaction as their durable acknowledgement.
A retry of the same request returns its original result without duplicating the entry.
Rejected or failed controls do not appear as completed actions.
Machine-generated `public.operational_events` remain separate from operator-authored entries.

## Use the Private API

All routes below require a named, run-scoped viewer session.
Mutations also require the existing `X-CSRF-Token`, allowed `Origin`, and
`Idempotency-Key` headers.
Reuse a key only when retrying the same unchanged request.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/v1/viewer/shift-logs` | Read shared submitted handovers and the current operator's current-run draft |
| GET | `/v1/runs/{run_id}/shift-logs` | Read the operator's shift records and entries |
| POST | `/v1/runs/{run_id}/shift-logs/entries` | Append `{ "kind": "note", "text": "Reviewed the power trend." }` |
| POST | `/v1/runs/{run_id}/shift-logs/{shift_id}/summary` | Save `{ "summary": "Next shift should recheck the trend." }` |
| POST | `/v1/runs/{run_id}/shift-logs/{shift_id}/submit` | Submit the draft with `{}` |

Use the running service's `/docs` for generated request and response schemas.
These private operator records are not added to public telemetry, viewer bootstrap,
or consumer exports.

See [validation evidence](../validation/shift-log.md) for local checks and limits.

## Model Reference

The following definitions are rendered directly from Python during documentation builds.

::: metis_sim.domain.shift_log

::: metis_sim.adapters.shift_log
