"""Transactional configuration, run lifecycle and committed telemetry writes."""

from collections import defaultdict
from datetime import timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, insert, or_, select, update

from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.adapters.records import (
    append_immutable,
    canonical_hash,
    log_rows,
    prior_result,
    record_result,
    utc_now,
)
from metis_sim.adapters.shift_log import append_control_action
from metis_sim.application.errors import ServiceError

Idempotent = tuple[str, str, str]
TERMINAL = {"completed", "stopped", "failed", "aborted"}


class Repository:
    """Write atomic simulation batches through a single private persistence port.

    Parameters
    ----------
    database : Database
        Connection and writer-lock owner.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def existing(self, token: Idempotent) -> dict[str, Any] | None:
        """Return the saved acknowledgement for an exact mutation retry."""
        with self.database.engine.connect() as connection:
            return prior_result(connection, *token)

    def save_configuration(
        self,
        configuration: dict[str, Any],
        resolved: dict[str, Any],
        digest: str,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Create an immutable revision and its idempotency record atomically."""
        with self.database.writer_transaction() as connection:
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            result = {
                "configuration_id": str(uuid4()),
                "canonical_hash": digest,
                "schema_version": "simulation.v1",
            }
            connection.execute(
                insert(tables.configurations).values(
                    configuration_id=result["configuration_id"],
                    canonical_hash=digest,
                    configuration=configuration,
                    resolved=resolved,
                    created_at=utc_now(),
                )
            )
            record_result(connection, *token, result)
            return result

    def configuration(self, configuration_id: str) -> dict[str, Any]:
        """Read a private revision for authorized application use."""
        with self.database.engine.connect() as connection:
            row = (
                connection.execute(
                    select(tables.configurations).where(
                        tables.configurations.c.configuration_id == configuration_id
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise ServiceError("configuration_not_found", "Configuration does not exist.", 404)
        return dict(row)

    def create_run(
        self,
        configuration_id: str,
        status: dict[str, Any],
        manifest: dict[str, Any],
        retain: bool,
        token: Idempotent,
        *,
        user_id: str | None = None,
        catalog_versions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Allocate a new run and its independent streams in one transaction.

        Parameters
        ----------
        configuration_id : str
            Saved immutable configuration revision.
        status, manifest : dict
            Separate public run projection and private reproducibility record.
        retain : bool
            Exempt the run from ordinary history expiration.
        token : Idempotent
            Durable mutation identity.
        user_id : str, optional
            Registered operator owning the run; legacy runs may remain anonymous.
        catalog_versions : dict of str to str, optional
            Complete satellite-to-catalog mapping from the validated profile.
            Omission supports callers producing the legacy power catalog.

        Returns
        -------
        dict
            The committed public run projection.
        """
        if catalog_versions is not None and set(catalog_versions) != {
            satellite["satellite_id"] for satellite in status["satellites"]
        }:
            raise ValueError("catalog_versions must cover exactly the run satellites")
        with self.database.writer_transaction() as connection:
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            connection.execute(
                insert(tables.runs).values(
                    run_id=status["run_id"],
                    configuration_id=configuration_id,
                    source_id=self.database.source_id,
                    user_id=user_id,
                    status=status["status"],
                    public_status=status,
                    manifest=manifest,
                    retain=retain,
                )
            )
            connection.execute(
                insert(tables.streams),
                [
                    dict(
                        stream_id=s["stream_id"],
                        source_id=self.database.source_id,
                        satellite_id=s["satellite_id"],
                        run_id=status["run_id"],
                        catalog_version=(catalog_versions or {}).get(
                            s["satellite_id"], "power-leo.v1"
                        ),
                        first_sequence=0,
                        last_sequence=-1,
                        expired=False,
                    )
                    for s in status["satellites"]
                ],
            )
            record_result(connection, *token, status)
        return status

    def expired_operator_runs(self, at_time: float) -> list[tuple[str, str]]:
        """Find active mock-owned runs whose durable browser lease has expired.

        Parameters
        ----------
        at_time : float
            Wall-clock UTC timestamp used to compare private lease deadlines.

        Returns
        -------
        list of tuple of str and str
            Run and operator IDs scoped to this service's source. Legacy runs
            without a user or a lease are never selected.
        """
        with self.database.engine.connect() as connection:
            rows = connection.execute(
                select(tables.runs.c.run_id, tables.runs.c.user_id).where(
                    tables.runs.c.source_id == self.database.source_id,
                    tables.runs.c.user_id.is_not(None),
                    tables.runs.c.status.in_({"running", "paused"}),
                    tables.runs.c.manifest["viewer_expires_at"].as_float() <= at_time,
                )
            )
            return [(row.run_id, row.user_id) for row in rows]

    def private_run(self, run_id: str) -> dict[str, Any]:
        """Load a private record; callers must project any public output."""
        with self.database.engine.connect() as connection:
            row = (
                connection.execute(select(tables.runs).where(tables.runs.c.run_id == run_id))
                .mappings()
                .first()
            )
        if row is None:
            raise ServiceError("run_not_found", "Run does not exist.", 404)
        return dict(row)

    def status(self, run_id: str) -> dict[str, Any]:
        """Return only the explicit public run projection."""
        with self.database.engine.connect() as connection:
            value = connection.execute(
                select(tables.runs.c.public_status).where(tables.runs.c.run_id == run_id)
            ).scalar_one_or_none()
        if value is None:
            raise ServiceError("run_not_found", "Run does not exist.", 404)
        return dict(value)

    def commit(
        self,
        status: dict[str, Any],
        frames: list[dict[str, Any]],
        events: list[dict[str, Any]],
        truth: list[dict[str, Any]],
        token: Idempotent | None = None,
        *,
        user_id: str | None = None,
        action: str | None = None,
        speed: int | None = None,
    ) -> dict[str, Any]:
        """Atomically append immutable outputs, update clock and acknowledge control.

        Parameters
        ----------
        status : dict
            Last fully computed tick and public lifecycle projection.
        frames, events, truth : list of dict
            Frozen outputs reused unchanged after a failed transaction.
        token : tuple, optional
            Request identity whose result commits with this boundary.
        user_id : str, optional
            Authenticated command actor; omitted for autonomous transitions.
        action : str, optional
            Successful simulation command to record in the actor's shift.
        speed : int, optional
            Requested speed for a set_speed command.

        Returns
        -------
        dict
            Durable acknowledgement, including for identical retries.
        """
        run_id = status["run_id"]
        with self.database.writer_transaction() as connection:
            if token is not None:
                existing = prior_result(connection, *token)
                if existing is not None:
                    return existing
            previous = connection.execute(
                select(tables.runs.c.public_status)
                .where(tables.runs.c.run_id == run_id)
                .with_for_update()
            ).scalar_one()
            if status["committed_tick"] < previous["committed_tick"]:
                raise ServiceError(
                    "committed_clock_regression", "The committed clock cannot move backwards."
                )
            status["status_revision"] = previous.get("status_revision", 0) + 1
            append_immutable(connection, tables.frames, log_rows(run_id, frames, "sequence"))
            append_immutable(connection, tables.events, log_rows(run_id, events, "event_sequence"))
            append_immutable(
                connection,
                tables.truth,
                [
                    dict(
                        run_id=run_id,
                        satellite_id=p["satellite_id"],
                        sequence=p["sequence"],
                        payload_hash=canonical_hash(p),
                        payload=p,
                    )
                    for p in truth
                ],
            )
            tails: dict[str, int] = defaultdict(lambda: -1)
            for frame in frames:
                tails[frame["stream_id"]] = max(tails[frame["stream_id"]], frame["sequence"])
            for stream_id, tail in tails.items():
                connection.execute(
                    update(tables.streams)
                    .where(
                        tables.streams.c.stream_id == stream_id,
                        tables.streams.c.last_sequence < tail,
                    )
                    .values(last_sequence=tail)
                )
            values: dict[str, Any] = {"status": status["status"], "public_status": status}
            if status["status"] in TERMINAL:
                values["ended_at"] = utc_now()
            connection.execute(
                update(tables.runs).where(tables.runs.c.run_id == run_id).values(**values)
            )
            if user_id is not None and action is not None:
                append_control_action(connection, status, user_id, action, speed)
            if token is not None:
                record_result(connection, *token, status)
        return status

    def recover(self) -> list[str]:
        """Abort orphaned active runs and finalize truth at their committed boundaries."""
        with self.database.engine.connect() as connection:
            orphaned = (
                connection.execute(
                    select(tables.runs.c.run_id).where(
                        tables.runs.c.source_id == self.database.source_id,
                        tables.runs.c.status.in_(["running", "paused"]),
                    )
                )
                .scalars()
                .all()
            )
        for run_id in orphaned:
            state = self.status(run_id)
            state.update(status="aborted", effective_speed=0, diagnostic="process_restarted")
            self.commit(state, [], [], self.final_truth(run_id, "aborted"))
        return list(orphaned)

    def final_truth(self, run_id: str, reason: str) -> list[dict[str, Any]]:
        """Preserve observed outcomes; censor all other series at the final committed tick."""
        status = self.status(run_id)
        if status.get("source_kind") == "observed":
            return []
        result = []
        with self.database.engine.connect() as connection:
            for satellite in status["satellites"]:
                last = connection.execute(
                    select(tables.truth.c.payload)
                    .where(
                        tables.truth.c.run_id == run_id,
                        tables.truth.c.satellite_id == satellite["satellite_id"],
                    )
                    .order_by(tables.truth.c.sequence.desc())
                    .limit(1)
                ).scalar_one_or_none()
                record = dict(
                    last or {"satellite_id": satellite["satellite_id"], "failure_tick": None}
                )
                record.update(
                    sequence=status["committed_tick"] + 1,
                    tick=status["committed_tick"],
                    observed_at=status["committed_at"],
                    terminal_reason=reason,
                    right_censored=record.get("failure_tick") is None,
                )
                result.append(record)
        return result

    def expire_terminal(self, days: int = 7) -> int:
        """Expire only unretained terminal history by wall termination time."""
        with self.database.writer_transaction() as connection:
            ids = list(
                connection.execute(
                    select(tables.runs.c.run_id).where(
                        tables.runs.c.status.in_(TERMINAL),
                        tables.runs.c.retain.is_(False),
                        tables.runs.c.ended_at < utc_now() - timedelta(days=days),
                    )
                ).scalars()
            )
            if not ids:
                return 0
            for table in [tables.frames, tables.events, tables.truth]:
                connection.execute(delete(table).where(table.c.run_id.in_(ids)))
            connection.execute(
                update(tables.streams).where(tables.streams.c.run_id.in_(ids)).values(expired=True)
            )
            return len(ids)

    def prune_abandoned_viewer_runs(self, max_age_s: int) -> list[str]:
        """Delete expired never-started browser runs and their private revisions.

        Parameters
        ----------
        max_age_s : int
            Minimum revision age; callers use longer than the cookie lifetime.

        Returns
        -------
        list of str
            Deleted run IDs whose in-memory engines may be released.

        Notes
        -----
        Only viewer-owned ``created`` runs qualify. Their streams have no
        samples, and valid browser cookies outlive neither the age threshold
        nor this cleanup. Associated idempotency replies are removed only
        after the same threshold, preventing stale run/config responses.
        """
        cutoff = utc_now() - timedelta(seconds=max_age_s)
        with self.database.writer_transaction() as connection:
            rows = list(
                connection.execute(
                    select(tables.runs.c.run_id, tables.runs.c.configuration_id)
                    .join(
                        tables.configurations,
                        tables.runs.c.configuration_id == tables.configurations.c.configuration_id,
                    )
                    .where(
                        tables.runs.c.source_id == self.database.source_id,
                        tables.runs.c.status == "created",
                        tables.runs.c.retain.is_(False),
                        tables.runs.c.manifest["viewer_owned"].as_boolean().is_(True),
                        tables.configurations.c.created_at < cutoff,
                        ~select(tables.shift_logs.c.shift_id)
                        .where(tables.shift_logs.c.run_id == tables.runs.c.run_id)
                        .exists(),
                    )
                    .limit(100)
                ).mappings()
            )
            if not rows:
                return []
            run_ids = [row["run_id"] for row in rows]
            configuration_ids = [row["configuration_id"] for row in rows]
            connection.execute(
                delete(tables.idempotency).where(
                    or_(
                        tables.idempotency.c.response["run_id"].as_string().in_(run_ids),
                        tables.idempotency.c.response["configuration_id"]
                        .as_string()
                        .in_(configuration_ids),
                    )
                )
            )
            connection.execute(delete(tables.streams).where(tables.streams.c.run_id.in_(run_ids)))
            connection.execute(delete(tables.runs).where(tables.runs.c.run_id.in_(run_ids)))
            connection.execute(
                delete(tables.configurations).where(
                    tables.configurations.c.configuration_id.in_(configuration_ids)
                )
            )
            return run_ids
