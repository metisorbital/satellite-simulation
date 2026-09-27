"""Durable private operator cases with immutable committed-public evidence."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import Connection

from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.adapters.records import prior_result, record_result, utc_now
from metis_sim.adapters.shift_log import append_operator_entry
from metis_sim.application.errors import ServiceError
from metis_sim.domain.catalog import CHANNELS_BY_CATALOG
from metis_sim.domain.telemetry import MeasurementFrame

Idempotent = tuple[str, str, str]
SHIFT_LOG_TEXT_LIMIT = 4000


def _timestamp(value: datetime | None) -> str | None:
    """Serialize a database timestamp with an explicit UTC offset."""
    return value.replace(tzinfo=value.tzinfo or UTC).isoformat() if value else None


def _validate_actor(connection: Connection, run_id: str, user_id: str) -> None:
    """Verify a named operator owns the run before a private case write."""
    owner = connection.execute(
        select(tables.runs.c.user_id).where(tables.runs.c.run_id == run_id)
    ).first()
    if owner is None:
        raise ServiceError("run_not_found", "Run does not exist.", 404)
    if owner.user_id != user_id:
        raise ServiceError("run_forbidden", "This run belongs to another operator.", 403)
    if (
        connection.execute(
            select(tables.users.c.user_id).where(tables.users.c.user_id == user_id)
        ).first()
        is None
    ):
        raise ServiceError("operator_not_found", "Operator identity does not exist.", 403)


def _value_text(value: object) -> str:
    """Render one already-validated public reading without changing its meaning."""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _evidence_from_frame(row: Any) -> dict[str, Any]:
    """Copy an allowlisted committed public frame into private case evidence."""
    # Stored public envelopes are JSON decoded by the driver, so UUIDs and
    # RFC 3339 timestamps arrive as strings. Validate the same canonical JSON
    # representation clients receive, retaining MeasurementFrame strictness.
    frame = MeasurementFrame.model_validate_json(
        json.dumps(row["payload"], ensure_ascii=False, separators=(",", ":"))
    )
    catalog = CHANNELS_BY_CATALOG[frame.catalog_version]
    readings = [
        {
            "channel_id": channel_id,
            "value_text": _value_text(reading.value),
            "quality": reading.quality,
            "unit": catalog[channel_id].unit,
        }
        for channel_id, reading in sorted(frame.channels.items())
    ]
    return {
        "source_id": frame.source_id,
        "stream_id": str(frame.stream_id),
        "satellite_id": frame.satellite_id,
        "payload_hash": row["payload_hash"],
        "sequence": frame.sequence,
        "observed_at": frame.observed_at.isoformat(),
        "emitted_at": frame.emitted_at.isoformat(),
        "committed_at": _timestamp(row["committed_at"]),
        "captured_at": _timestamp(utc_now()),
        "catalog_version": frame.catalog_version,
        "source_kind": frame.source_kind,
        "time_domain": frame.time_domain,
        "readings": readings,
    }


def _capture_evidence(
    connection: Connection,
    run_id: str,
    satellite_id: str,
    sequence: int | None,
    *,
    required: bool,
) -> dict[str, Any] | None:
    """Capture one committed public frame from the case's own stream.

    Parameters
    ----------
    connection : Connection
        Caller-owned transaction or read connection.
    run_id, satellite_id : str
        Logical run and satellite that define the only eligible stream.
    sequence : int or None
        Exact stream sequence, or the latest committed frame when omitted.
    required : bool
        Whether no committed frame is an error instead of a nullable capture.

    Returns
    -------
    dict or None
        Self-contained public evidence, or ``None`` for a newly created case
        before its first committed sample.
    """
    stream = (
        connection.execute(
            select(tables.streams.c.stream_id).where(
                tables.streams.c.run_id == run_id,
                tables.streams.c.satellite_id == satellite_id,
            )
        )
        .scalars()
        .first()
    )
    if stream is None:
        raise ServiceError("satellite_not_found", "Satellite does not belong to this run.", 422)
    statement = select(
        tables.frames.c.payload, tables.frames.c.committed_at, tables.frames.c.payload_hash
    ).where(tables.frames.c.stream_id == stream)
    if sequence is not None:
        statement = statement.where(tables.frames.c.sequence == sequence)
    else:
        statement = statement.order_by(tables.frames.c.sequence.desc()).limit(1)
    row = connection.execute(statement).mappings().first()
    if row is None:
        if required:
            raise ServiceError(
                "committed_sample_not_found",
                "No committed public sample is available for this case.",
                409,
            )
        return None
    return _evidence_from_frame(row)


def _append_activity(
    connection: Connection,
    case_id: str,
    user_id: str,
    kind: str,
    text: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    """Append an immutable server-authored audit event to one owned case."""
    connection.execute(
        insert(tables.case_activities).values(
            activity_id=str(uuid4()),
            case_id=case_id,
            user_id=user_id,
            kind=kind,
            text=text,
            evidence=evidence,
            created_at=utc_now(),
        )
    )


def _shift_entry_text(case_id: str, title: str, narrative: str) -> str:
    """Bound a linked Shift Log entry while retaining case identity and disclosure."""
    prefix = f"Case {case_id}: {title}\n"
    text = prefix + narrative
    if len(text) <= SHIFT_LOG_TEXT_LIMIT:
        return text
    suffix = "\nFull details in case history."
    retained = SHIFT_LOG_TEXT_LIMIT - len(prefix) - len(suffix)
    return prefix + narrative[:retained] + suffix


class CaseRepository:
    """Persist private operator-authored case state and append-only history.

    Parameters
    ----------
    database : Database
        Existing single-writer transaction owner.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def list_cases(self, user_id: str) -> dict[str, Any]:
        """List at most 100 historical cases owned by one named operator.

        Parameters
        ----------
        user_id : str
            Authenticated named operator identity.

        Returns
        -------
        dict
            Private case projections ordered by most recent update.
        """
        with self.database.engine.connect() as connection:
            total = connection.execute(
                select(func.count())
                .select_from(tables.operator_cases)
                .where(tables.operator_cases.c.user_id == user_id)
            ).scalar_one()
            rows = connection.execute(
                select(
                    tables.operator_cases.c.case_id,
                    tables.operator_cases.c.run_id,
                    tables.operator_cases.c.user_id,
                    tables.operator_cases.c.satellite_id,
                    tables.operator_cases.c.title,
                    tables.operator_cases.c.summary,
                    tables.operator_cases.c.priority,
                    tables.operator_cases.c.status,
                    tables.operator_cases.c.decision,
                    tables.operator_cases.c.outcome,
                    tables.operator_cases.c.revision,
                    tables.operator_cases.c.created_at,
                    tables.operator_cases.c.updated_at,
                )
                .where(tables.operator_cases.c.user_id == user_id)
                .order_by(
                    tables.operator_cases.c.updated_at.desc(), tables.operator_cases.c.case_id
                )
                .limit(100)
            ).mappings()
            return {
                "items": [
                    {
                        **{
                            key: row[key]
                            for key in (
                                "case_id",
                                "run_id",
                                "user_id",
                                "satellite_id",
                                "title",
                                "summary",
                                "priority",
                                "status",
                                "decision",
                                "outcome",
                                "revision",
                            )
                        },
                        "created_at": _timestamp(row["created_at"]),
                        "updated_at": _timestamp(row["updated_at"]),
                    }
                    for row in rows
                ],
                "total": total,
                "has_more": total > 100,
            }

    def detail(self, case_id: str, user_id: str) -> dict[str, Any]:
        """Read one complete private case only for its named owner.

        Parameters
        ----------
        case_id, user_id : str
            Requested case and authenticated named operator identity.

        Returns
        -------
        dict
            Full case with bounded activity timeline and evidence snapshots.
        """
        with self.database.engine.connect() as connection:
            exists = connection.execute(
                select(tables.operator_cases.c.case_id).where(
                    tables.operator_cases.c.case_id == case_id,
                    tables.operator_cases.c.user_id == user_id,
                )
            ).scalar_one_or_none()
            if exists is None:
                raise ServiceError("case_not_found", "Case does not exist.", 404)
            return self._read(connection, case_id)

    def create(
        self,
        run_id: str,
        user_id: str,
        satellite_id: str,
        title: str,
        summary: str,
        priority: str,
        sequence: int | None,
        token: Idempotent,
        *,
        model_case_id: str | None = None,
        model_recommendation: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create an owned case and capture its selected committed public frame.

        Parameters
        ----------
        run_id, user_id, satellite_id : str
            Authorized current run, authenticated operator, and public stream satellite.
        title, summary, priority : str
            Validated operator-authored case inputs.
        sequence : int or None
            Exact public stream sequence, or the current committed tail.
        token : tuple of str
            Idempotency scope, key, and canonical request digest.
        model_case_id : str or None
            Deterministic server-owned identity for a saved model warning. It
            prevents duplicate investigations even after retry records expire.
        model_recommendation : dict of str, optional
            Server-authored prediction recommendation, expected effect, and
            tradeoffs. These are narrative planning claims, never evidence.

        Returns
        -------
        dict
            Created private case with its initial activity.

        The initial evidence remains nullable only when a new run has not
        committed a sample. It is otherwise copied from the exact selected
        sequence or current stream tail and never recalculated.
        """
        with self.database.writer_transaction() as connection:
            _validate_actor(connection, run_id, user_id)
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            if model_case_id is not None:
                prior_case = connection.execute(
                    select(tables.operator_cases.c.case_id).where(
                        tables.operator_cases.c.case_id == model_case_id,
                        tables.operator_cases.c.user_id == user_id,
                        tables.operator_cases.c.run_id == run_id,
                    )
                ).scalar_one_or_none()
                if prior_case is not None:
                    return self._read(connection, prior_case)
            evidence = _capture_evidence(
                connection, run_id, satellite_id, sequence, required=sequence is not None
            )
            case_id = model_case_id or str(uuid4())
            prediction = model_recommendation or {}
            now = utc_now()
            connection.execute(
                insert(tables.operator_cases).values(
                    case_id=case_id,
                    run_id=run_id,
                    user_id=user_id,
                    satellite_id=satellite_id,
                    title=title,
                    summary=summary,
                    priority=priority,
                    status="open",
                    assessment="",
                    missing_information="",
                    recommendation=prediction.get("recommendation", ""),
                    expected_effect=prediction.get("expected_effect", ""),
                    tradeoffs=prediction.get("tradeoffs", ""),
                    decision="pending",
                    decision_reason="",
                    outcome="awaiting_observation",
                    outcome_notes="",
                    revision=1,
                    evidence=evidence,
                    created_at=now,
                    updated_at=now,
                )
            )
            _append_activity(
                connection,
                case_id,
                user_id,
                "created",
                "Saved model prediction raised for operator review. Evidence contains only committed telemetry."
                if model_case_id
                else "Case created.",
                evidence,
            )
            append_operator_entry(
                connection,
                run_id,
                user_id,
                "event",
                _shift_entry_text(case_id, title, f"Created:\n{summary}"),
            )
            if prediction:
                text = (
                    f"Saved model recommendation: {prediction['recommendation']}\n"
                    f"Expected effect: {prediction['expected_effect']}\n"
                    f"Tradeoffs: {prediction['tradeoffs']}\nAwaiting operator approval."
                )
                _append_activity(connection, case_id, user_id, "recommendation", text)
                append_operator_entry(
                    connection,
                    run_id,
                    user_id,
                    "event",
                    _shift_entry_text(case_id, title, text),
                )
            result = self._read(connection, case_id)
            record_result(connection, *token, result)
            return result

    def record_demo_result(
        self, run_id: str, user_id: str, case_id: str | None, text: str, token: Idempotent
    ) -> None:
        """Append a labeled scenario result without deciding the human case outcome.

        Parameters
        ----------
        run_id, user_id : str
            Existing recorded replay and its authenticated owner.
        case_id : str or None
            Prediction case if Metis raised one; disabled runs use Shift Log only.
        text : str
            Explicitly labeled demo projection, never measured execution evidence.
        token : tuple
            Stable result identity preventing duplicate audit entries after retries.
        """
        with self.database.writer_transaction() as connection:
            _validate_actor(connection, run_id, user_id)
            if prior_result(connection, *token) is not None:
                return
            if case_id is not None:
                case = self._owned_case(connection, case_id, user_id)
                if case["run_id"] != run_id:
                    raise ServiceError(
                        "mission_case_mismatch", "The demo result belongs to another run.", 409
                    )
                self._update_revision(connection, case_id, case["revision"], {})
                _append_activity(connection, case_id, user_id, "outcome", text)
                text = _shift_entry_text(case_id, case["title"], text)
            append_operator_entry(connection, run_id, user_id, "event", text)
            record_result(connection, *token, {"recorded": True})

    def assessment(
        self,
        case_id: str,
        user_id: str,
        revision: int,
        assessment: str,
        missing_information: str,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Store operator assessment text at the expected revision.

        Parameters
        ----------
        case_id, user_id : str
            Case identity and authenticated owner identity.
        revision : int
            Client-observed case revision required for the mutation.
        assessment, missing_information : str
            Validated operator-authored review fields.
        token : tuple of str
            Idempotency scope, key, and canonical request digest.

        Returns
        -------
        dict
            Updated case and append-only audit activity.
        """
        return self._change(
            case_id,
            user_id,
            revision,
            token,
            values={"assessment": assessment, "missing_information": missing_information},
            kind="assessment",
            text=f"Assessment: {assessment}\nMissing information: {missing_information}",
        )

    def recommendation(
        self,
        case_id: str,
        user_id: str,
        revision: int,
        recommendation: str,
        expected_effect: str,
        tradeoffs: str,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Store an operator-authored recommendation at the expected revision.

        Parameters
        ----------
        case_id, user_id : str
            Case identity and authenticated owner identity.
        revision : int
            Client-observed case revision required for the mutation.
        recommendation, expected_effect, tradeoffs : str
            Validated operator-authored decision-support material.
        token : tuple of str
            Idempotency scope, key, and canonical request digest.

        Returns
        -------
        dict
            Updated case, with prior decision and outcome state reset.
        """
        return self._change(
            case_id,
            user_id,
            revision,
            token,
            values={
                "recommendation": recommendation,
                "expected_effect": expected_effect,
                "tradeoffs": tradeoffs,
                "decision": "pending",
                "decision_reason": "",
                "outcome": "awaiting_observation",
                "outcome_notes": "",
            },
            kind="recommendation",
            text=(
                f"Recommendation: {recommendation}\n"
                f"Expected effect: {expected_effect}\n"
                f"Tradeoffs: {tradeoffs}"
            ),
        )

    def decision(
        self,
        case_id: str,
        user_id: str,
        revision: int,
        decision: str,
        reason: str,
        revised_recommendation: str | None,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Record a human approval, rejection, or revision decision.

        Parameters
        ----------
        case_id, user_id : str
            Case identity and authenticated owner identity.
        revision : int
            Client-observed case revision required for the mutation.
        decision, reason, revised_recommendation : str or None
            Validated human decision and its explanation, with replacement
            recommendation only for a revised decision.
        token : tuple of str
            Idempotency scope, key, and canonical request digest.

        Returns
        -------
        dict
            Updated case and immutable decision audit activity.
        """
        values: dict[str, Any] = {"decision": decision, "decision_reason": reason}
        if revised_recommendation is not None:
            values.update(
                recommendation=revised_recommendation,
                outcome="awaiting_observation",
                outcome_notes="",
            )
        return self._change(
            case_id,
            user_id,
            revision,
            token,
            values=values,
            kind="decision",
            text=(
                f"Decision: {decision}\nReason: {reason}"
                + (
                    f"\nRevised recommendation: {revised_recommendation}"
                    if revised_recommendation is not None
                    else ""
                )
            ),
            require_recommendation=True,
        )

    def outcome(
        self,
        case_id: str,
        user_id: str,
        revision: int,
        outcome: str,
        outcome_notes: str,
        close_case: bool,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Record an observation result separately from a decision.

        Parameters
        ----------
        case_id, user_id : str
            Case identity and authenticated owner identity.
        revision : int
            Client-observed case revision required for the mutation.
        outcome, outcome_notes : str
            Validated observed result and supporting manual narrative.
        close_case : bool
            Explicit case lifecycle choice made with the outcome.
        token : tuple of str
            Idempotency scope, key, and canonical request digest.

        Returns
        -------
        dict
            Updated case and immutable outcome audit activity.
        """
        return self._change(
            case_id,
            user_id,
            revision,
            token,
            values={
                "outcome": outcome,
                "outcome_notes": outcome_notes,
                "status": "closed" if close_case else "open",
            },
            kind="outcome",
            text=(
                f"Outcome: {outcome}\nNotes: {outcome_notes}\n"
                f"Case closed: {'yes' if close_case else 'no'}"
            ),
        )

    def capture_evidence(
        self,
        case_id: str,
        user_id: str,
        revision: int,
        current_run_id: str,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Append the current committed public frame from the case's own run.

        Parameters
        ----------
        case_id, user_id : str
            Case identity and authenticated owner identity.
        revision : int
            Client-observed case revision required for the mutation.
        current_run_id : str
            Session's currently scoped run, which must match case provenance.
        token : tuple of str
            Idempotency scope, key, and canonical request digest.

        Returns
        -------
        dict
            Updated case with a later immutable public evidence activity.
        """
        with self.database.writer_transaction() as connection:
            row = self._owned_case(connection, case_id, user_id)
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            self._require_open(row)
            self._require_revision(row, revision)
            if row["run_id"] != current_run_id:
                raise ServiceError(
                    "case_run_forbidden",
                    "Evidence can only be captured while viewing the case's original run.",
                    403,
                )
            evidence = _capture_evidence(
                connection, row["run_id"], row["satellite_id"], None, required=True
            )
            self._update_revision(connection, case_id, row["revision"])
            _append_activity(
                connection, case_id, user_id, "evidence", "Evidence captured.", evidence
            )
            append_operator_entry(
                connection,
                row["run_id"],
                user_id,
                "event",
                _shift_entry_text(case_id, row["title"], "Evidence captured."),
            )
            result = self._read(connection, case_id)
            record_result(connection, *token, result)
            return result

    def _change(
        self,
        case_id: str,
        user_id: str,
        revision: int,
        token: Idempotent,
        *,
        values: dict[str, Any],
        kind: str,
        text: str,
        require_recommendation: bool = False,
    ) -> dict[str, Any]:
        """Apply one revision-checked case mutation and append its audit activity."""
        with self.database.writer_transaction() as connection:
            row = self._owned_case(connection, case_id, user_id)
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            self._require_open(row)
            self._require_revision(row, revision)
            if require_recommendation and not row["recommendation"].strip():
                raise ServiceError(
                    "recommendation_required",
                    "Record a nonblank recommendation before a decision.",
                    409,
                )
            self._update_revision(connection, case_id, row["revision"], values)
            _append_activity(connection, case_id, user_id, kind, text)
            append_operator_entry(
                connection,
                row["run_id"],
                user_id,
                "decision" if kind == "decision" else "event",
                _shift_entry_text(case_id, row["title"], text),
            )
            result = self._read(connection, case_id)
            record_result(connection, *token, result)
            return result

    @staticmethod
    def _owned_case(connection: Connection, case_id: str, user_id: str) -> dict[str, Any]:
        """Lock and return one case only when it belongs to the named operator."""
        row = (
            connection.execute(
                select(tables.operator_cases)
                .where(
                    tables.operator_cases.c.case_id == case_id,
                    tables.operator_cases.c.user_id == user_id,
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ServiceError("case_not_found", "Case does not exist.", 404)
        return dict(row)

    @staticmethod
    def _require_revision(row: dict[str, Any], revision: int) -> None:
        """Reject a stale optimistic-concurrency version before any write."""
        if row["revision"] != revision:
            raise ServiceError(
                "case_revision_conflict",
                "Case changed; reload it before saving.",
                409,
                [{"current_revision": row["revision"]}],
            )

    @staticmethod
    def _require_open(row: dict[str, Any]) -> None:
        """Reject workflow mutations after the operator has explicitly closed a case."""
        if row["status"] == "closed":
            raise ServiceError("case_closed", "Closed cases are read-only.", 409)

    @staticmethod
    def _update_revision(
        connection: Connection,
        case_id: str,
        prior_revision: int,
        values: dict[str, Any] | None = None,
    ) -> None:
        """Persist one locked case revision and its server timestamp."""
        connection.execute(
            update(tables.operator_cases)
            .where(
                tables.operator_cases.c.case_id == case_id,
                tables.operator_cases.c.revision == prior_revision,
            )
            .values(**(values or {}), revision=prior_revision + 1, updated_at=utc_now())
        )

    @staticmethod
    def _read(connection: Connection, case_id: str) -> dict[str, Any]:
        """Project one private row to its strict response allowlist."""
        row = (
            connection.execute(
                select(tables.operator_cases).where(tables.operator_cases.c.case_id == case_id)
            )
            .mappings()
            .one()
        )
        fields = (
            "case_id",
            "run_id",
            "user_id",
            "satellite_id",
            "title",
            "summary",
            "priority",
            "status",
            "assessment",
            "missing_information",
            "recommendation",
            "expected_effect",
            "tradeoffs",
            "decision",
            "decision_reason",
            "outcome",
            "outcome_notes",
            "revision",
            "evidence",
        )
        result = {field: row[field] for field in fields}
        result.update({field: _timestamp(row[field]) for field in ("created_at", "updated_at")})
        activity_count = connection.execute(
            select(func.count())
            .select_from(tables.case_activities)
            .where(tables.case_activities.c.case_id == case_id)
        ).scalar_one()
        activities = list(
            connection.execute(
                select(tables.case_activities)
                .where(tables.case_activities.c.case_id == case_id)
                .order_by(
                    tables.case_activities.c.created_at.desc(),
                    tables.case_activities.c.activity_id.desc(),
                )
                .limit(50)
            ).mappings()
        )
        result["activities"] = [
            {
                "activity_id": activity["activity_id"],
                "case_id": activity["case_id"],
                "user_id": activity["user_id"],
                "kind": activity["kind"],
                "text": activity["text"],
                "created_at": _timestamp(activity["created_at"]),
                "evidence": activity["evidence"],
            }
            for activity in reversed(activities)
        ]
        result["activity_count"] = activity_count
        result["activities_truncated"] = activity_count > len(activities)
        return result
