"""Storage outage, writer-session ownership, and immutable replay regressions."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from metis_sim.adapters.database import Database
from metis_sim.adapters.repository import Repository
from metis_sim.api.app import create_app
from metis_sim.application.errors import ServiceError
from metis_sim.application.runner import PendingCommand, Runner
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from tests.integration.conftest import create_run, operator_headers
from tests.integration.test_service import wait_completed


def _postgres_settings(settings):
    url = os.environ.get("METIS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set METIS_TEST_DATABASE_URL to run actual PostgreSQL gates")
    return replace(settings, database_url=url, source_id="test-" + uuid4().hex)


def test_paused_status_read_recovers_without_failing_run(client, configuration, monkeypatch):
    """Treat a paused writer's transient status failure as bounded backpressure."""
    configuration["run"]["duration_s"] = 100
    run = create_run(client, configuration)
    control = f"/v1/runs/{run['run_id']}/control"
    assert (
        client.post(
            control, json={"action": "start"}, headers=operator_headers("start")
        ).status_code
        == 200
    )
    paused = client.post(
        control, json={"action": "pause"}, headers=operator_headers("pause")
    ).json()
    context = client.app.state
    original_status, original_wait = context.repository.status, context.runner._wait
    failed, retrying, recovered = threading.Event(), threading.Event(), threading.Event()

    def transient_read(run_id):
        if threading.current_thread() is context.runner.thread and not failed.is_set():
            failed.set()
            raise OperationalError("injected transient read timeout", {}, None)
        return original_status(run_id)

    def observe_retry(event, timeout):
        if context.runner.backpressure:
            retrying.set()
        elif retrying.is_set():
            recovered.set()
        return original_wait(event, timeout)

    monkeypatch.setattr(context.repository, "status", transient_read)
    monkeypatch.setattr(context.runner, "_wait", observe_retry)
    assert recovered.wait(3), "Writer must recover through its persistence retry path"
    status = original_status(run["run_id"])
    assert status["status"] == "paused" and status["committed_tick"] == paused["committed_tick"]
    assert context.runner.failure is None and not context.runner.backpressure


def test_read_outage_budget_stops_without_publishing_terminal_state():
    """An exhausted status read leaves the last durable state for restart recovery."""
    repository = Mock(spec=Repository)
    repository.status.side_effect = OperationalError("persistent read outage", {}, None)
    wall = [0.0]

    def advance_clock(event, timeout):
        if runner.failure:
            runner.stop_event.set()
        else:
            wall[0] += 30
        return event.is_set()

    runner = Runner(repository, monotonic=lambda: wall[0], wait=advance_clock)
    runner.active_id = "run"
    runner._loop()
    assert runner.failure == "persistence_unavailable" and runner.backpressure
    assert repository.status.call_count == 1
    repository.commit.assert_not_called()
    repository.final_truth.assert_not_called()


def test_command_read_failure_guarantees_no_late_application():
    """A control that cannot read its boundary fails without entering a transaction."""
    repository = Mock(spec=Repository)
    repository.existing.return_value = None
    repository.status.side_effect = OperationalError("command status unavailable", {}, None)
    runner = Runner(repository, monotonic=lambda: 0)
    command = PendingCommand("run", "pause", None, ("scope", "key", "hash"), 5)
    runner.commands.put_nowait(command)
    runner._drain_commands()
    with pytest.raises(ServiceError) as failure:
        command.result.result()
    assert failure.value.code == "control_not_applied"
    repository.commit.assert_not_called()


def test_terminal_truth_read_recovers_before_single_commit():
    """A transient censoring read cannot prematurely mark the run failed."""
    repository = Mock(spec=Repository)
    repository.final_truth.side_effect = [OperationalError("truth read timeout", {}, None), []]
    repository.commit.side_effect = lambda status, *args: status
    wall = [0.0]

    def advance_clock(event, timeout):
        wall[0] += timeout
        return False

    runner = Runner(repository, monotonic=lambda: wall[0], wait=advance_clock)
    result = runner._terminal({"run_id": "run", "status": "paused"}, "stopped")
    assert result["status"] == "stopped" and repository.final_truth.call_count == 2
    assert repository.commit.call_count == 1 and runner.failure is None


def test_shutdown_does_not_spin_through_persistence_retry_delay():
    """Stopping the loop cannot turn storage backoff into an already-set event."""
    repository = Mock(spec=Repository)
    repository.commit.side_effect = OperationalError("write outage", {}, None)
    wall = [0.0]
    waits = []

    def advance_clock(event, timeout):
        waits.append(timeout)
        assert not event.is_set()
        wall[0] = 30
        return False

    runner = Runner(repository, monotonic=lambda: wall[0], wait=advance_clock)
    runner.stop_event.set()
    with pytest.raises(ServiceError) as failure:
        runner._commit({"run_id": "run"}, [], [], [])
    assert failure.value.code == "persistence_unavailable" and waits == [0.25]
    assert repository.commit.call_count == 1


def test_duplicate_old_frame_cannot_regress_advertised_stream_tail(client, configuration):
    """An accepted immutable duplicate preserves the current discovery watermark."""
    run = create_run(client, configuration)
    client.post(
        f"/v1/runs/{run['run_id']}/control",
        json={"action": "start"},
        headers=operator_headers("start"),
    )
    final = wait_completed(client, run["run_id"])
    context = client.app.state
    frame = context.reader.snapshot(run["run_id"], history=41)["frames"][0]
    context.repository.commit(final, [frame], [], [])
    streams = context.reader.streams(run["run_id"])
    assert all(stream["last_sequence"] == final["committed_tick"] for stream in streams)


@pytest.mark.parametrize("action,speed", [("resume", None), ("set_speed", 20)])
def test_noop_controls_preserve_pacing_anchors(action, speed):
    """A durable no-op acknowledgement cannot advance the next tick or reset metrics."""
    repository = Mock(spec=Repository)
    repository.existing.return_value = None
    repository.status.return_value = {
        "run_id": "run",
        "status": "running",
        "requested_speed": 20,
        "committed_tick": 10,
        "effective_speed": 18.5,
    }
    repository.commit.side_effect = lambda status, *args: status
    runner = Runner(repository, monotonic=lambda: 100)
    runner._next_due, runner._pace_wall, runner._metrics_wall = 103, 90, 95
    runner._pace_tick, runner._metrics_tick = 2, 8
    runner._apply(PendingCommand("run", action, speed, ("scope", "key", "hash"), 105))
    assert (runner._next_due, runner._pace_wall, runner._metrics_wall) == (103, 90, 95)
    assert (runner._pace_tick, runner._metrics_tick) == (2, 8)
    assert repository.commit.call_count == 1


@pytest.mark.parametrize(
    "state,action,speed", [("running", "set_speed", 5), ("paused", "resume", None)]
)
def test_actual_pacing_changes_reset_wall_anchor(state, action, speed):
    """A resumed clock or changed running speed establishes a new wall-time target."""
    repository = Mock(spec=Repository)
    repository.existing.return_value = None
    repository.status.return_value = {
        "run_id": "run",
        "status": state,
        "requested_speed": 20,
        "committed_tick": 10,
        "effective_speed": 0,
    }
    repository.commit.side_effect = lambda status, *args: status
    runner = Runner(repository, monotonic=lambda: 100)
    runner._next_due, runner._pace_wall, runner._metrics_wall = 103, 90, 95
    runner._apply(PendingCommand("run", action, speed, ("scope", "key", "hash"), 105))
    assert (runner._next_due, runner._pace_wall, runner._metrics_wall) == (100, 100, 100)
    assert (runner._pace_tick, runner._metrics_tick) == (10, 10)


@pytest.mark.postgres
def test_postgres_writer_session_probes_are_serialized_and_idle(settings, monkeypatch):
    """Health and writes share one lock-owning connection without an idle transaction."""
    settings = _postgres_settings(settings)
    database = Database(settings.database_url, settings.source_id)
    try:
        database.acquire_writer()
        connection = database._lock_connection
        assert connection is not None and not connection.in_transaction()
        with database.writer_transaction() as writer:
            pid = writer.execute(text("SELECT pg_backend_pid()")).scalar_one()
        with database.engine.connect() as observer:
            state = observer.execute(
                text("SELECT state, xact_start FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}
            ).one()
        assert state.state == "idle" and state.xact_start is None
        original = connection.execute
        guard = threading.Lock()
        active, maximum = 0, 0

        def observed_execute(*args, **kwargs):
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
            try:
                time.sleep(0.01)
                return original(*args, **kwargs)
            finally:
                with guard:
                    active -= 1

        monkeypatch.setattr(connection, "execute", observed_execute)
        with ThreadPoolExecutor(max_workers=4) as pool:
            assert all(pool.map(lambda _: database.healthy(), range(8)))
        assert maximum == 1 and not connection.in_transaction()
    finally:
        database.close()


@pytest.mark.postgres
def test_postgres_statement_timeout_preserves_writer_session(settings):
    """A cancelled statement rolls back its short transaction while retaining ownership."""
    settings = _postgres_settings(settings)
    database = Database(settings.database_url, settings.source_id)
    try:
        database.acquire_writer()
        connection = database._lock_connection
        with pytest.raises(OperationalError):
            with database.writer_transaction() as writer:
                writer.execute(text("SET LOCAL statement_timeout = 1"))
                writer.execute(text("SELECT pg_sleep(0.02)"))
        assert database.healthy()
        assert database._lock_connection is connection
        assert connection is not None and not connection.in_transaction()
    finally:
        database.close()


@pytest.mark.postgres
def test_lost_postgres_writer_session_never_reconnects_or_writes(settings, configuration):
    """A terminated advisory session stops the runner and leaves its durable run untouched."""
    settings = _postgres_settings(settings)
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        run = create_run(client, configuration, uuid4().hex)
        database = app.state.database
        with database.writer_transaction() as writer:
            pid = writer.execute(text("SELECT pg_backend_pid()")).scalar_one()
        with database.engine.begin() as observer:
            assert observer.execute(
                text("SELECT pg_terminate_backend(:pid)"), {"pid": pid}
            ).scalar_one()
        response = client.post(
            f"/v1/runs/{run['run_id']}/control",
            json={"action": "start"},
            headers=operator_headers(uuid4().hex),
        )
        assert response.status_code == 503 and response.json()["code"] == "writer_ownership_lost"
        assert app.state.runner.failure == "writer_ownership_lost" and not database.healthy()
        assert app.state.repository.status(run["run_id"])["status"] == "created"
        assert (
            client.post(
                "/v1/configurations", json=configuration, headers=operator_headers(uuid4().hex)
            ).status_code
            == 503
        )
        assert (
            client.post(
                f"/v1/operator/runs/{run['run_id']}/viewer-session",
                json={},
                headers=operator_headers(uuid4().hex),
            ).status_code
            == 503
        )
        with pytest.raises(ServiceError, match="ownership is unavailable"):
            app.state.repository.expire_terminal()
        with pytest.raises(ServiceError, match="ownership was lost"):
            database.acquire_writer()
        competitor = Database(settings.database_url, settings.source_id)
        try:
            competitor.acquire_writer()
            assert competitor.healthy()
            with pytest.raises(ServiceError, match="ownership is unavailable"):
                with database.writer_transaction():
                    pytest.fail("Lost writer must never obtain another transaction")
        finally:
            competitor.close()


@pytest.mark.postgres
def test_shared_database_idempotency_is_scoped_to_source(settings, configuration):
    """Independent source owners cannot replay one another's mutation acknowledgements."""
    first_settings = _postgres_settings(settings)
    second_settings = replace(first_settings, source_id="test-" + uuid4().hex)
    first_app = create_app(first_settings, setup_schema=True, prepare_demo=False)
    second_app = create_app(second_settings, setup_schema=True, prepare_demo=False)
    key = uuid4().hex
    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        first_run = create_run(first_client, configuration, key)
        second_run = create_run(second_client, configuration, key)
        assert first_run["run_id"] != second_run["run_id"]
        for client, run, expected in (
            (first_client, first_run, first_settings.source_id),
            (second_client, second_run, second_settings.source_id),
        ):
            streams = client.app.state.reader.streams(run["run_id"])
            assert {stream["source_id"] for stream in streams} == {expected}
            assert create_run(client, configuration, key) == run
