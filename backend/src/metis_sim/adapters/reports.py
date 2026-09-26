"""Read a watermark-bounded telemetry report from the durable public log."""

from typing import Any

from sqlalchemy import select

from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.application.errors import ServiceError
from metis_sim.application.reporting import ChannelAccumulator
from metis_sim.domain.catalog import CATALOGS
from metis_sim.domain.reports import StreamSummary, TelemetryReport


def telemetry_report(
    database: Database, run_id: str, start: int = 0, end: int | None = None
) -> TelemetryReport:
    """Summarize one committed window with bounded memory and no future health.

    Parameters
    ----------
    database : Database
        Durable public frame log and run watermark.
    run_id : str
        Authorized run to read.
    start, end : int and int or None
        Inclusive sequence bounds. The default end captures the current watermark.

    Returns
    -------
    TelemetryReport
        Per-stream coverage, quality counts, and explicitly weighted statistics.

    Raises
    ------
    ServiceError
        If the run is absent, history expired, or bounds include future samples.
    """
    with database.engine.connect() as connection:
        # One read transaction also prevents retention deletion during the read
        # on SQLite; PostgreSQL uses a repeatable snapshot for all queries.
        if connection.dialect.name == "postgresql":
            connection = connection.execution_options(isolation_level="REPEATABLE READ")
        with connection.begin():
            if connection.dialect.name == "sqlite":
                connection.exec_driver_sql("BEGIN")
            status = connection.execute(
                select(tables.runs.c.public_status).where(tables.runs.c.run_id == run_id)
            ).scalar_one_or_none()
            if status is None:
                raise ServiceError("run_not_found", "Run does not exist.", 404)
            watermark = status["committed_tick"]
            stop = watermark if end is None else end
            if (
                start < 0
                or start > max(0, watermark)
                or (end is not None and (end < start or end > watermark))
            ):
                raise ServiceError(
                    "invalid_window", "Report bounds must describe committed samples.", 422
                )
            streams = (
                connection.execute(
                    select(tables.streams)
                    .where(tables.streams.c.run_id == run_id)
                    .order_by(tables.streams.c.satellite_id)
                )
                .mappings()
                .all()
            )
            if any(stream["expired"] for stream in streams):
                raise ServiceError("history_expired", "Run telemetry has expired.", 410)
            results = []
            for stream in streams:
                catalog = CATALOGS[stream["catalog_version"]]
                accumulators = {item.channel_id: ChannelAccumulator(item) for item in catalog}
                first: dict[str, Any] | None = None
                last: dict[str, Any] | None = None
                count = 0
                statement = (
                    select(tables.frames.c.payload)
                    .where(
                        tables.frames.c.stream_id == stream["stream_id"],
                        tables.frames.c.sequence >= start,
                        tables.frames.c.sequence <= stop,
                    )
                    .order_by(tables.frames.c.sequence)
                    .execution_options(yield_per=500)
                )
                for frame in connection.execute(statement).scalars():
                    if first is None:
                        first = frame
                    last = frame
                    count += 1
                    for key, accumulator in accumulators.items():
                        accumulator.add(frame["channels"].get(key), frame["sample_window_s"])
                expected = max(0, stop - start + 1)
                results.append(
                    StreamSummary(
                        source_id=stream["source_id"],
                        stream_id=stream["stream_id"],
                        satellite_id=stream["satellite_id"],
                        catalog_version=stream["catalog_version"],
                        frame_count=count,
                        expected_frame_count=expected,
                        complete_window=count == expected,
                        first_sequence=first["sequence"] if first else None,
                        last_sequence=last["sequence"] if last else None,
                        first_observed_at=first["observed_at"] if first else None,
                        last_observed_at=last["observed_at"] if last else None,
                        channels=[accumulator.result() for accumulator in accumulators.values()],
                    )
                )
            return TelemetryReport(
                run_id=run_id,
                run_status=status["status"],
                committed_tick=watermark,
                from_sequence=start,
                through_sequence=stop,
                model_provenance=status["model_provenance"],
                streams=results,
            )
