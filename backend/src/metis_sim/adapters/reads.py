"""Public replay and consistent snapshots, isolated from private manifest access."""

from datetime import datetime, timedelta
from typing import Any

from itsdangerous import BadData, URLSafeSerializer
from sqlalchemy import func, select

from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.application.errors import ServiceError
from metis_sim.domain.telemetry import MAX_SAFE_INTEGER


def sequence_watermark(status: dict[str, Any]) -> int:
    """Return the committed sample index independently of elapsed source time.

    Parameters
    ----------
    status : dict
        Public run status, including older physics records without a sequence field.

    Returns
    -------
    int
        Last durable sample sequence, or ``-1`` before the first sample.
    """
    sequence = status.get("committed_sequence")
    return status["committed_tick"] if sequence is None else sequence


class PublicReader:
    """Read only public projections and logs through opaque scoped cursors.

    Parameters
    ----------
    database : Database
        Durable transactional store.
    cursor_secret : str
        Stable deployment secret for authenticating opaque cursor content.
    """

    def __init__(self, database: Database, cursor_secret: str) -> None:
        self.database = database
        self.cursors = URLSafeSerializer(cursor_secret, salt="metis-cursor-v1")

    def streams(self, run_id: str | None = None) -> list[dict[str, Any]]:
        """List producer-neutral stream identities and retained sequence bounds."""
        statement = select(tables.streams, tables.runs.c.public_status).join(
            tables.runs, tables.runs.c.run_id == tables.streams.c.run_id
        )
        if run_id:
            statement = statement.where(tables.streams.c.run_id == run_id)
        with self.database.engine.connect() as connection:
            return [
                {
                    **{key: value for key, value in row.items() if key != "public_status"},
                    "source_kind": row["public_status"].get("source_kind", "synthetic"),
                    "time_domain": row["public_status"].get("time_domain", "simulation_utc"),
                }
                for row in connection.execute(statement).mappings()
            ]

    def stream_run(self, stream_id: str) -> str:
        """Resolve a stream for authorization without exposing its private run record."""
        with self.database.engine.connect() as connection:
            run_id = connection.execute(
                select(tables.streams.c.run_id).where(tables.streams.c.stream_id == stream_id)
            ).scalar_one_or_none()
        if run_id is None:
            raise ServiceError("stream_not_found", "Stream does not exist.", 404)
        return str(run_id)

    def page(
        self,
        stream_id: str,
        after: str | None,
        limit: int,
        kind: str = "telemetry",
        *,
        from_sequence: int | None = None,
        through_sequence: int | None = None,
        from_observed_at: datetime | None = None,
        through_observed_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Read retained public envelopes by cursor or committed telemetry range.

        Parameters
        ----------
        stream_id : str
            Public stream whose history is being read.
        after : str or None
            Opaque prior cursor, ``latest`` for the current tail, or None for
            the earliest retained item.
        limit : int
            Maximum number of items in this page.
        kind : str, default='telemetry'
            ``telemetry`` or ``events``; each has a separate sequence space.
        from_sequence, through_sequence : int or None
            Inclusive telemetry bounds, incompatible with ``after``. Omitted
            endpoints default to zero and the captured committed watermark.
            Continue a bounded read with another numeric range, not its cursor.
        from_observed_at, through_observed_at : datetime or None
            Inclusive original observation-time bounds. Combine with sequence
            bounds for keyset pagination; timestamps require a UTC offset.

        Returns
        -------
        dict[str, Any]
            Items, next cursor, more-data flag, retained bounds, and delivery
            mode. An empty page still includes a usable next cursor.

        Raises
        ------
        ServiceError
            If the stream, cursor, or committed range is invalid, or history expired.
        """
        bounded = any(
            value is not None
            for value in (from_sequence, through_sequence, from_observed_at, through_observed_at)
        )
        if bounded and (after is not None or kind != "telemetry"):
            raise ServiceError(
                "invalid_window", "Sequence bounds require telemetry without a cursor.", 422
            )
        if bounded and any(
            value is not None and (type(value) is not int or not 0 <= value <= MAX_SAFE_INTEGER)
            for value in (from_sequence, through_sequence)
        ):
            raise ServiceError(
                "invalid_window", "Sequence bounds exceed the exact JSON range.", 422
            )
        if any(
            value is not None and (value.tzinfo is None or value.utcoffset() is None)
            for value in (from_observed_at, through_observed_at)
        ):
            raise ServiceError("invalid_time", "Observation bounds require a UTC offset.", 422)
        if (
            from_observed_at is not None
            and through_observed_at is not None
            and from_observed_at > through_observed_at
        ):
            raise ServiceError("invalid_window", "Observation-time bounds are reversed.", 422)
        table = tables.frames if kind == "telemetry" else tables.events
        sequence = table.c.sequence if kind == "telemetry" else table.c.event_sequence
        with self.database.engine.begin() as connection:
            stream = (
                connection.execute(
                    select(tables.streams).where(tables.streams.c.stream_id == stream_id)
                )
                .mappings()
                .first()
            )
            if stream is None:
                raise ServiceError("stream_not_found", "Stream does not exist.", 404)
            stop = None
            start = 0 if from_sequence is None else from_sequence
            if bounded:
                status = connection.execute(
                    select(tables.runs.c.public_status).where(
                        tables.runs.c.run_id == stream["run_id"]
                    )
                ).scalar_one()
                watermark = sequence_watermark(status)
                stop = watermark if through_sequence is None else through_sequence
                if stop < start or stop > watermark:
                    raise ServiceError(
                        "invalid_window", "Sequence bounds must describe committed samples.", 422
                    )
                if through_observed_at is not None:
                    source_clock = datetime.fromisoformat(
                        status["epoch_utc"].replace("Z", "+00:00")
                    ) + timedelta(seconds=status["committed_tick"])
                    if through_observed_at > source_clock:
                        raise ServiceError(
                            "future_health_forbidden", "Observation window must be committed.", 422
                        )
            bounds = connection.execute(
                select(func.min(sequence), func.max(sequence)).where(table.c.stream_id == stream_id)
            ).one()
            retained = {"first_sequence": bounds[0], "last_sequence": bounds[1]}
            if stream["expired"]:
                raise ServiceError(
                    "cursor_expired",
                    "History expired; explicit resynchronization is required.",
                    410,
                    [retained],
                )
            position = start - 1 if bounded else -1
            if after == "latest":
                position = bounds[1] if bounds[1] is not None else -1
            elif after:
                try:
                    cursor = self.cursors.loads(after)
                except BadData as error:
                    raise ServiceError("invalid_cursor", "Cursor is invalid.", 422) from error
                if (
                    not isinstance(cursor, dict)
                    or cursor.get("version") != 1
                    or cursor.get("kind") != kind
                    or cursor.get("stream_id") != stream_id
                    or type(cursor.get("position")) is not int
                ):
                    raise ServiceError(
                        "invalid_cursor",
                        "Cursor belongs to a different stream or sequence namespace.",
                        422,
                    )
                position = cursor["position"]
                if bounds[0] is not None and position + 1 < bounds[0]:
                    raise ServiceError(
                        "cursor_expired",
                        "History expired; explicit resynchronization is required.",
                        410,
                        [retained],
                    )
            statement = select(table.c.payload).where(
                table.c.stream_id == stream_id, sequence > position
            )
            if stop is not None:
                statement = statement.where(sequence <= stop)
            if from_observed_at is not None:
                statement = statement.where(table.c.observed_at >= from_observed_at)
            if through_observed_at is not None:
                statement = statement.where(table.c.observed_at <= through_observed_at)
            rows = list(connection.execute(statement.order_by(sequence).limit(limit + 1)).scalars())
            more = len(rows) > limit
            items = rows[:limit]
            if items:
                position = items[-1][sequence.name]
            cursor = self.cursors.dumps(
                dict(version=1, kind=kind, stream_id=stream_id, position=position)
            )
            return dict(
                items=items,
                next_cursor=cursor,
                has_more=more,
                retained_range=retained,
                delivery_mode="replay",
            )

    def snapshot(self, run_id: str, at: datetime | None = None, history: int = 1) -> dict[str, Any]:
        """Read a coherent committed boundary; never include health after that instant."""
        with self.database.engine.begin() as connection:
            # Capture the committed watermark first. Subsequent queries are explicitly
            # bounded by it even under PostgreSQL READ COMMITTED isolation.
            status = connection.execute(
                select(tables.runs.c.public_status).where(tables.runs.c.run_id == run_id)
            ).scalar_one_or_none()
            if status is None:
                raise ServiceError("run_not_found", "Run does not exist.", 404)
            tick = sequence_watermark(status)
            if at is not None:
                if at.tzinfo is None:
                    raise ServiceError("invalid_time", "Snapshot time requires a UTC offset.", 422)
                observed_bound = (
                    datetime.fromisoformat(status["epoch_utc"].replace("Z", "+00:00"))
                    + timedelta(seconds=status["committed_tick"])
                    if status.get("source_kind") == "observed"
                    else datetime.fromisoformat(status["committed_at"].replace("Z", "+00:00"))
                    if status["committed_at"] is not None
                    else None
                )
                if observed_bound is None or at > observed_bound:
                    raise ServiceError(
                        "future_health_forbidden", "Health snapshots must be committed.", 422
                    )
                sample = connection.execute(
                    select(func.max(tables.frames.c.sequence)).where(
                        tables.frames.c.run_id == run_id,
                        tables.frames.c.observed_at <= at,
                        tables.frames.c.sequence <= tick,
                    )
                ).scalar_one()
                if sample is None:
                    raise ServiceError(
                        "snapshot_not_found", "No retained sample precedes this instant.", 404
                    )
                tick = sample
            frames = list(
                connection.execute(
                    select(tables.frames.c.payload)
                    .where(
                        tables.frames.c.run_id == run_id,
                        tables.frames.c.sequence <= tick,
                        tables.frames.c.sequence > tick - history,
                    )
                    .order_by(tables.frames.c.sequence, tables.frames.c.stream_id)
                ).scalars()
            )
            if at is not None and frames:
                elapsed = int(
                    (
                        datetime.fromisoformat(frames[-1]["observed_at"].replace("Z", "+00:00"))
                        - datetime.fromisoformat(status["epoch_utc"].replace("Z", "+00:00"))
                    ).total_seconds()
                )
                status = {
                    **status,
                    "committed_tick": elapsed,
                    "committed_at": frames[-1]["observed_at"],
                    **(
                        {"committed_sequence": tick}
                        if status.get("data_source") == "satellitecots"
                        else {}
                    ),
                }
            return {"status": status, "frames": frames}

    def private_truth(self, run_id: str, after: int = -1, limit: int = 500) -> dict[str, Any]:
        """Read evaluator-only truth by a deterministic run-wide row offset."""
        with self.database.engine.connect() as connection:
            values = list(
                connection.execute(
                    select(tables.truth.c.payload)
                    .where(tables.truth.c.run_id == run_id)
                    .order_by(tables.truth.c.sequence, tables.truth.c.satellite_id)
                    .offset(after + 1)
                    .limit(limit + 1)
                ).scalars()
            )
        items = values[:limit]
        return {"items": items, "next_offset": after + len(items), "has_more": len(values) > limit}
