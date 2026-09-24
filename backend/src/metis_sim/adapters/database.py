"""Connection ownership and single-writer exclusion."""

import hashlib
import shutil
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool

from metis_sim.adapters.tables import metadata
from metis_sim.application.errors import ServiceError


class Database:
    """Own one SQLAlchemy engine and the producer's lifetime writer lock.

    Parameters
    ----------
    url : str
        PostgreSQL URL; SQLite is supported only for isolated local tests/demo.
    source_id : str
        Identity protected against simultaneous writer processes.
    """

    def __init__(self, url: str, source_id: str) -> None:
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        elif url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://") :]
        options: dict[str, Any] = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            options["connect_args"] = {"check_same_thread": False, "timeout": 2}
            options["execution_options"] = {
                "schema_translate_map": {"private": None, "public": None}
            }
            if ":memory:" in url:
                options["poolclass"] = StaticPool
        else:
            options["connect_args"] = {"connect_timeout": 3, "options": "-c statement_timeout=3000"}
        self.engine: Engine = create_engine(url, **options)
        self.source_id = source_id
        self._lock_connection: Connection | None = None
        self._lock_file: Any = None
        self._writer_mutex = threading.RLock()
        self._writer_acquired = False
        self._ownership_lost = False
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", self._sqlite_setup)

    @staticmethod
    def _sqlite_setup(connection: Any, _: Any) -> None:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")

    def create_test_schema(self) -> None:
        """Create isolated test tables; production uses explicit Alembic migrations."""
        with self.engine.begin() as connection:
            if self.engine.dialect.name == "postgresql":
                connection.execute(text("CREATE SCHEMA IF NOT EXISTS private"))
            metadata.create_all(connection)

    def acquire_writer(self) -> None:
        """Fail readiness if another process already owns the source identity."""
        with self._writer_mutex:
            if self._ownership_lost:
                raise ServiceError(
                    "writer_ownership_lost",
                    "Writer ownership was lost; restart to recover safely.",
                    503,
                )
            if self._writer_acquired:
                return
            if self.engine.dialect.name == "postgresql":
                connection = self.engine.connect()
                key = int.from_bytes(
                    hashlib.sha256(self.source_id.encode()).digest()[:8], "big", signed=True
                )
                try:
                    if not connection.execute(
                        text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
                    ).scalar():
                        raise ServiceError(
                            "writer_already_owned", "Another process owns this source.", 503
                        )
                    # This is a session lock: commit the acquisition transaction
                    # and retain the same physical connection for every write.
                    connection.commit()
                except BaseException:
                    connection.invalidate()
                    connection.close()
                    raise
                self._lock_connection = connection
            elif self.engine.url.database and self.engine.url.database != ":memory:":
                import fcntl

                path = Path(str(self.engine.url.database) + ".writer.lock")
                handle = path.open("a")
                try:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as error:
                    handle.close()
                    raise ServiceError(
                        "writer_already_owned", "Another process owns this database.", 503
                    ) from error
                self._lock_file = handle
            self._writer_acquired = True

    @contextmanager
    def writer_transaction(self) -> Iterator[Connection]:
        """Commit a serialized write on the session that owns the advisory lock.

        Yields
        ------
        Connection
            Transaction-scoped writer connection. PostgreSQL session loss aborts
            its writes and cannot silently reconnect without the advisory lock.

        Raises
        ------
        ServiceError
            If this instance has not acquired, or has permanently lost, ownership.
        SQLAlchemyError
            If the transaction fails; its changes are rolled back for retry.
        """
        with self._writer_mutex:
            if not self._writer_acquired or self._ownership_lost:
                raise ServiceError(
                    "writer_ownership_lost",
                    "Writer ownership is unavailable; restart to recover safely.",
                    503,
                )
            connection = self._lock_connection
            if self.engine.dialect.name == "postgresql":
                if connection is None or connection.closed or connection.invalidated:
                    self._ownership_lost = True
                    raise ServiceError(
                        "writer_ownership_lost",
                        "Writer connection was lost; restart to recover safely.",
                        503,
                    )
                try:
                    with connection.begin():
                        yield connection
                except SQLAlchemyError:
                    if connection.closed or connection.invalidated:
                        self._ownership_lost = True
                    raise
            else:
                if self._lock_file is not None and self._lock_file.closed:
                    self._ownership_lost = True
                    raise ServiceError(
                        "writer_ownership_lost",
                        "Writer lock was lost; restart to recover safely.",
                        503,
                    )
                with self.engine.begin() as connection:
                    yield connection

    def healthy(self) -> bool:
        """Probe the owning connection in a short serialized transaction.

        Returns
        -------
        bool
            Whether the writer still owns its lock and the database responds.

        Raises
        ------
        SQLAlchemyError
            On a transient probe failure, distinct from permanent ownership loss.
        """
        try:
            with self.writer_transaction() as connection:
                return connection.execute(text("SELECT 1")).scalar() == 1
        except ServiceError:
            return False

    def storage_stats(self) -> dict[str, int]:
        """Measure database size and host headroom without inspecting telemetry content."""
        size = 0
        if self.engine.dialect.name == "postgresql":
            with self.engine.connect() as connection:
                size = int(
                    connection.execute(
                        text("SELECT pg_database_size(current_database())")
                    ).scalar_one()
                )
        elif self.engine.url.database and self.engine.url.database != ":memory:":
            path = Path(self.engine.url.database)
            size = sum(
                item.stat().st_size for item in (path, Path(str(path) + "-wal")) if item.exists()
            )
        return {"database_bytes": size, "host_free_bytes": shutil.disk_usage(Path.cwd()).free}

    def close(self) -> None:
        """Release writer ownership and pooled connections."""
        with self._writer_mutex:
            self._ownership_lost = True
            self._writer_acquired = False
            if self._lock_connection is not None:
                # Returning a session-locked connection to the pool would retain
                # its advisory lock. Close its physical connection explicitly.
                self._lock_connection.invalidate()
                self._lock_connection.close()
                self._lock_connection = None
            if self._lock_file is not None:
                self._lock_file.close()
                self._lock_file = None
            self.engine.dispose()
