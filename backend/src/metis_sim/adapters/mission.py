"""Durable mission snapshots bound to the recorded run and named operator."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.application.errors import ServiceError


class MissionRepository:
    """Store one mission snapshot per run and operator.

    Parameters
    ----------
    database : Database
        Transaction owner for the existing mission database.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _check_owner(connection: Connection, run_id: str, user_id: str) -> None:
        """Require an existing run owned by the named operator.

        Parameters
        ----------
        connection : Connection
            Connection used for the current read or write.
        run_id : str
            Run to check.
        user_id : str
            Authenticated operator identifier.

        Raises
        ------
        ServiceError
            If the run or operator does not exist, or ownership differs.
        """
        row = connection.execute(
            select(tables.runs.c.user_id).where(tables.runs.c.run_id == run_id)
        ).first()
        if row is None:
            raise ServiceError("run_not_found", "Run does not exist.", 404)
        if row.user_id != user_id:
            raise ServiceError("run_forbidden", "This run belongs to another operator.", 403)
        if (
            connection.execute(
                select(tables.users.c.user_id).where(tables.users.c.user_id == user_id)
            ).first()
            is None
        ):
            raise ServiceError("operator_not_found", "Operator identity does not exist.", 403)

    def get(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        """Read an owned run's mission snapshot.

        Parameters
        ----------
        run_id : str
            Existing run identifier.
        user_id : str
            Authenticated operator identifier.

        Returns
        -------
        dict or None
            Independent JSON snapshot, if one has been saved.
        """
        with self.database.engine.connect() as connection:
            self._check_owner(connection, run_id, user_id)
            state = connection.execute(
                select(tables.mission_states.c.state).where(
                    tables.mission_states.c.run_id == run_id,
                    tables.mission_states.c.user_id == user_id,
                )
            ).scalar_one_or_none()
            return deepcopy(state) if state is not None else None

    def list_pending(self) -> list[dict[str, Any]]:
        """Read source-owned missions waiting for an alert or operator decision.

        Returns
        -------
        list of dict
            Independent unresolved snapshots. This internal recovery read is
            scoped to the database writer's source.
        """
        with self.database.engine.connect() as connection:
            states = connection.execute(
                select(tables.mission_states.c.state)
                .join(tables.runs, tables.mission_states.c.run_id == tables.runs.c.run_id)
                .where(tables.runs.c.source_id == self.database.source_id)
            ).scalars()
            return [
                deepcopy(state)
                for state in states
                if state.get("status") in {"watching", "awaiting_decision"}
                or (
                    state.get("demo_result") is None
                    and state.get("status") in {"approved", "dismissed", "reviewed"}
                )
            ]

    def save(self, run_id: str, user_id: str, state: dict[str, Any]) -> None:
        """Insert or replace one owned mission snapshot atomically.

        Parameters
        ----------
        run_id : str
            Existing run identifier.
        user_id : str
            Authenticated operator identifier.
        state : dict
            JSON-compatible mission state with matching run and operator IDs.

        Raises
        ------
        ServiceError
            If ownership or the snapshot's identity is invalid.
        """
        if (
            not isinstance(state, dict)
            or state.get("run_id") != run_id
            or state.get("user_id") != user_id
        ):
            raise ServiceError(
                "invalid_mission_state", "Mission state identity differs from its run.", 422
            )
        with self.database.writer_transaction() as connection:
            self._check_owner(connection, run_id, user_id)
            current = connection.execute(
                select(tables.mission_states.c.state).where(
                    tables.mission_states.c.run_id == run_id,
                    tables.mission_states.c.user_id == user_id,
                )
            ).scalar_one_or_none()
            snapshot = deepcopy(state)
            if current is not None and current.get("case_id") and snapshot.get("case_id") is None:
                snapshot["case_id"] = current["case_id"]
            now = datetime.now(UTC)
            if current is None:
                connection.execute(
                    insert(tables.mission_states).values(
                        run_id=run_id,
                        user_id=user_id,
                        state=snapshot,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                connection.execute(
                    update(tables.mission_states)
                    .where(
                        tables.mission_states.c.run_id == run_id,
                        tables.mission_states.c.user_id == user_id,
                    )
                    .values(state=snapshot, updated_at=now)
                )
