"""Private, attributable operator handover records and atomic command history."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.adapters.records import prior_result, record_result, utc_now
from metis_sim.application.errors import ServiceError

Idempotent = tuple[str, str, str]


def _timestamp(value: datetime | None) -> str | None:
    return value.replace(tzinfo=value.tzinfo or UTC).isoformat() if value else None


def _validate_actor(connection: Connection, run_id: str, user_id: str) -> None:
    owner = connection.execute(
        select(tables.runs.c.user_id).where(tables.runs.c.run_id == run_id)
    ).first()
    if owner is None:
        raise ServiceError("run_not_found", "Run does not exist.", 404)
    if owner.user_id is not None and owner.user_id != user_id:
        raise ServiceError("run_forbidden", "This run belongs to another operator.", 403)
    if (
        connection.execute(
            select(tables.users.c.user_id).where(tables.users.c.user_id == user_id)
        ).first()
        is None
    ):
        raise ServiceError("operator_not_found", "Operator identity does not exist.", 403)


def _draft(connection: Connection, run_id: str, user_id: str) -> str:
    shift_id = connection.execute(
        select(tables.shift_logs.c.shift_id).where(
            tables.shift_logs.c.run_id == run_id,
            tables.shift_logs.c.user_id == user_id,
            tables.shift_logs.c.status == "draft",
        )
    ).scalar_one_or_none()
    if shift_id is None:
        shift_id = str(uuid4())
        now = utc_now()
        connection.execute(
            insert(tables.shift_logs).values(
                shift_id=shift_id,
                run_id=run_id,
                user_id=user_id,
                status="draft",
                summary="",
                created_at=now,
                updated_at=now,
                submitted_at=None,
            )
        )
    return shift_id


def _entry(
    connection: Connection,
    shift_id: str,
    user_id: str,
    kind: str,
    text: str,
    details: dict[str, Any],
) -> None:
    now = utc_now()
    connection.execute(
        insert(tables.shift_log_entries).values(
            entry_id=str(uuid4()),
            shift_id=shift_id,
            user_id=user_id,
            kind=kind,
            text=text,
            details=details,
            created_at=now,
        )
    )
    connection.execute(
        update(tables.shift_logs)
        .where(tables.shift_logs.c.shift_id == shift_id)
        .values(updated_at=now)
    )


def append_control_action(
    connection: Connection,
    status: dict[str, Any],
    user_id: str,
    action: str,
    speed: int | None,
) -> None:
    """Record a successful command within its caller's status transaction.

    Parameters
    ----------
    connection : Connection
        Existing transaction also saving the command acknowledgment.
    status : dict
        Committed public run status, used only for allowlisted context.
    user_id : str
        Authenticated actor; never inferred from run ownership.
    action : str
        Validated successful simulation command.
    speed : int or None
        Requested multiplier when changing simulation speed.
    """
    _validate_actor(connection, status["run_id"], user_id)
    shift_id = _draft(connection, status["run_id"], user_id)
    _entry(
        connection,
        shift_id,
        user_id,
        "action",
        f"Simulation {action} applied.",
        {
            "action": action,
            "speed": speed,
            "committed_tick": status["committed_tick"],
            "status": status["status"],
        },
    )


def append_operator_entry(
    connection: Connection,
    run_id: str,
    user_id: str,
    kind: str,
    text: str,
) -> None:
    """Append a non-control private operator event in a caller-owned transaction.

    Parameters
    ----------
    connection : Connection
        Existing transaction that owns the substantive private workflow write.
    run_id : str
        Owned logical run to associate with the operator's current handover draft.
    user_id : str
        Authenticated named operator; never sourced from request JSON.
    kind : {"note", "decision", "action", "unresolved_issue", "event"}
        Existing Shift Log category. Case workflow uses ``event`` or ``decision``.
    text : str
        Server-composed audit narrative. Control-only details remain empty.
    """
    _validate_actor(connection, run_id, user_id)
    shift_id = _draft(connection, run_id, user_id)
    _entry(connection, shift_id, user_id, kind, text, {})


class ShiftLogRepository:
    """Persist editable drafts and immutable submitted operator handovers.

    Parameters
    ----------
    database : Database
        Existing single-writer transaction owner.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_users(self, operators: list[dict[str, str]]) -> None:
        """Synchronize trusted operator profiles without changing historical IDs.

        Parameters
        ----------
        operators : list of dict
            Trusted identity directory with user_id, login and display_name.
        """
        with self.database.writer_transaction() as connection:
            for operator in operators:
                profile = {key: operator[key] for key in ("user_id", "login", "display_name")}
                if (
                    connection.execute(
                        select(tables.users.c.user_id).where(
                            tables.users.c.user_id == profile["user_id"]
                        )
                    ).first()
                    is None
                ):
                    connection.execute(insert(tables.users).values(**profile, created_at=utc_now()))
                else:
                    connection.execute(
                        update(tables.users)
                        .where(tables.users.c.user_id == profile["user_id"])
                        .values(**profile)
                    )

    def list_logs(self, run_id: str, user_id: str) -> dict[str, Any]:
        """Read an operator's handovers with explicit, private response fields.

        Parameters
        ----------
        run_id, user_id : str
            Authorized run and authenticated operator identity.

        Returns
        -------
        dict
            Items containing the operator's logs and their attributed entries.
        """
        with self.database.engine.connect() as connection:
            _validate_actor(connection, run_id, user_id)
            ids = connection.execute(
                select(tables.shift_logs.c.shift_id)
                .where(
                    tables.shift_logs.c.run_id == run_id,
                    tables.shift_logs.c.user_id == user_id,
                )
                .order_by(tables.shift_logs.c.created_at.desc(), tables.shift_logs.c.shift_id)
            ).scalars()
            return {"items": [self._read(connection, shift_id) for shift_id in ids]}

    def add_entry(
        self,
        run_id: str,
        user_id: str,
        kind: str,
        text: str,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Append an attributed entry to the current draft, creating one if needed.

        Parameters
        ----------
        run_id, user_id : str
            Authorized run and authenticated actor.
        kind, text : str
            Validated entry category and operator-authored text.
        token : tuple of str
            Scope, idempotency key and request hash.

        Returns
        -------
        dict
            Updated draft including its entries.
        """
        with self.database.writer_transaction() as connection:
            _validate_actor(connection, run_id, user_id)
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            shift_id = _draft(connection, run_id, user_id)
            _entry(connection, shift_id, user_id, kind, text, {})
            result = self._read(connection, shift_id)
            record_result(connection, *token, result)
            return result

    def update_summary(
        self,
        run_id: str,
        user_id: str,
        shift_id: str,
        summary: str,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Edit the handover summary while the owned shift is a draft.

        Parameters
        ----------
        run_id, user_id, shift_id : str
            Authorized run, authenticated actor and owned draft identity.
        summary : str
            Validated handover text.
        token : tuple of str
            Scope, idempotency key and request hash.

        Returns
        -------
        dict
            Updated draft with its original entries preserved.
        """
        return self._change(run_id, user_id, shift_id, token, summary=summary)

    def submit(
        self,
        run_id: str,
        user_id: str,
        shift_id: str,
        token: Idempotent,
    ) -> dict[str, Any]:
        """Freeze an owned draft as a submitted handover.

        Parameters
        ----------
        run_id, user_id, shift_id : str
            Authorized run, authenticated actor and owned draft identity.
        token : tuple of str
            Scope, idempotency key and request hash.

        Returns
        -------
        dict
            Submitted handover and its attributed entries.
        """
        return self._change(run_id, user_id, shift_id, token, submit=True)

    def _change(
        self,
        run_id: str,
        user_id: str,
        shift_id: str,
        token: Idempotent,
        *,
        summary: str | None = None,
        submit: bool = False,
    ) -> dict[str, Any]:
        with self.database.writer_transaction() as connection:
            _validate_actor(connection, run_id, user_id)
            row = (
                connection.execute(
                    select(tables.shift_logs)
                    .where(
                        tables.shift_logs.c.shift_id == shift_id,
                        tables.shift_logs.c.run_id == run_id,
                        tables.shift_logs.c.user_id == user_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ServiceError("shift_log_not_found", "Shift log does not exist.", 404)
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            if row["status"] != "draft":
                raise ServiceError(
                    "shift_log_submitted", "Submitted shift logs cannot be edited.", 409
                )
            now = utc_now()
            values: dict[str, Any] = {"updated_at": now}
            if summary is not None:
                values["summary"] = summary
            if submit:
                values.update(status="submitted", submitted_at=now)
            connection.execute(
                update(tables.shift_logs)
                .where(tables.shift_logs.c.shift_id == shift_id)
                .values(**values)
            )
            result = self._read(connection, shift_id)
            record_result(connection, *token, result)
            return result

    @staticmethod
    def _read(connection: Connection, shift_id: str) -> dict[str, Any]:
        row = (
            connection.execute(
                select(tables.shift_logs).where(tables.shift_logs.c.shift_id == shift_id)
            )
            .mappings()
            .one()
        )
        result = {key: row[key] for key in ("shift_id", "run_id", "user_id", "status", "summary")}
        result.update(
            {key: _timestamp(row[key]) for key in ("created_at", "updated_at", "submitted_at")}
        )
        result["entries"] = [
            {
                **{
                    key: entry[key]
                    for key in ("entry_id", "shift_id", "user_id", "kind", "text", "details")
                },
                "created_at": _timestamp(entry["created_at"]),
            }
            for entry in connection.execute(
                select(tables.shift_log_entries)
                .where(tables.shift_log_entries.c.shift_id == shift_id)
                .order_by(
                    tables.shift_log_entries.c.created_at, tables.shift_log_entries.c.entry_id
                )
            ).mappings()
        ]
        return result
