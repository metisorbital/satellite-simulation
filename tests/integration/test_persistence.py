"""Atomic rollback, restart, private censoring and production database gates."""

import copy
import os
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.api.app import create_app
from metis_sim.application.errors import ServiceError
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError

from tests.integration.conftest import create_run, operator_headers
from tests.integration.test_service import wait_completed


def test_failed_commit_does_not_publish_frames_or_clock(client, configuration):
    """Roll back telemetry and discovery bounds when the clock update fails."""
    run = create_run(client, configuration)
    run_id = run["run_id"]
    context = client.app.state
    prepared = context.runner.prepared[run_id]
    frames, events, truth = prepared.projector.project(prepared.engine.sample(0))
    status = {
        **run,
        "status": "running",
        "committed_tick": 0,
        "committed_at": frames[0]["observed_at"],
        "frame_count": 3,
    }

    def reject_clock_update(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE") and "runs" in statement:
            raise OperationalError("injected transaction failure", {}, None)

    event.listen(context.database.engine, "before_cursor_execute", reject_clock_update)
    try:
        with pytest.raises(OperationalError):
            context.repository.commit(status, frames, events, truth)
    finally:
        event.remove(context.database.engine, "before_cursor_execute", reject_clock_update)
    assert context.reader.snapshot(run_id)["frames"] == []
    assert context.repository.status(run_id)["committed_tick"] == -1
    assert all(stream["last_sequence"] == -1 for stream in context.reader.streams(run_id))
    context.repository.commit(status, frames, events, truth)
    assert {f["stream_id"]: f for f in context.reader.snapshot(run_id)["frames"]} == {
        f["stream_id"]: f for f in frames
    }


def test_writer_retry_preserves_identity_and_emission_time(client, configuration, monkeypatch):
    """Retry frozen batch contents without changing their public envelopes."""
    run = create_run(client, configuration)
    original = client.app.state.repository.commit
    retained = []
    failed = False

    def retry_once(status, frames, events, truth, token=None):
        nonlocal failed
        if frames and not failed:
            failed = True
            retained.extend(copy.deepcopy(frames))
            raise OperationalError("injected one-shot outage", {}, None)
        if frames and retained and frames[0]["sequence"] == retained[0]["sequence"]:
            assert frames == retained
        return original(status, frames, events, truth, token)

    monkeypatch.setattr(client.app.state.repository, "commit", retry_once)
    client.post(
        f"/v1/runs/{run['run_id']}/control",
        json={"action": "start"},
        headers=operator_headers("start"),
    )
    assert wait_completed(client, run["run_id"])["frame_count"] == 27
    snapshot = client.app.state.reader.snapshot(run["run_id"], history=41)
    by_identity = {(frame["stream_id"], frame["sequence"]): frame for frame in snapshot["frames"]}
    assert all(by_identity[(frame["stream_id"], frame["sequence"])] == frame for frame in retained)


def test_terminal_truth_preserves_observed_failure(client, configuration):
    """Retain private observed failure while excluding its cause from public events."""
    configuration["profiles"]["leo_power_demo"]["battery"]["initial_soc"] = 0.1
    configuration["scenario"] = [
        {
            "satellite_id": "METIS-01",
            "type": "solar_derating",
            "points": [{"at_s": 0, "multiplier": 1.0}],
            "outcome": {"type": "energy_reserve_violation", "reserve_soc": 0.15, "dwell_s": 1},
        }
    ]
    run = create_run(client, configuration)
    client.post(
        f"/v1/runs/{run['run_id']}/control",
        json={"action": "start"},
        headers=operator_headers("start"),
    )
    wait_completed(client, run["run_id"])
    truth = client.app.state.reader.private_truth(run["run_id"])["items"]
    terminal = next(
        item for item in truth if item["satellite_id"] == "METIS-01" and item["terminal_reason"]
    )
    assert terminal["failure_tick"] == 1
    assert terminal["right_censored"] is False
    events = client.app.state.reader.page(run["satellites"][0]["stream_id"], None, 200, "events")[
        "items"
    ]
    assert all(
        item["event_type"] not in {"low_energy_limit_entered", "injection_started"}
        for item in events
    )


def test_orphan_recovery_aborts_and_preserves_committed_history(settings, configuration):
    """Abort an orphan at its durable boundary and censor remaining private outcomes."""
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        run = create_run(client, configuration)
        prepared = app.state.runner.prepared[run["run_id"]]
        frames, events, truth = prepared.projector.project(prepared.engine.sample(0))
        state = {
            **run,
            "status": "running",
            "committed_tick": 0,
            "committed_at": frames[0]["observed_at"],
            "frame_count": 3,
        }
        app.state.repository.commit(state, frames, events, truth)
        # No runner owns this deliberately orphaned persisted state.
    recovered = create_app(settings, prepare_demo=False)
    with TestClient(recovered) as client:
        status = recovered.state.repository.status(run["run_id"])
        assert status["status"] == "aborted" and status["committed_tick"] == 0
        assert {
            f["stream_id"]: f for f in recovered.state.reader.snapshot(run["run_id"])["frames"]
        } == {f["stream_id"]: f for f in frames}
        truth = recovered.state.reader.private_truth(run["run_id"])["items"]
        assert all(item["right_censored"] for item in truth if item["terminal_reason"] == "aborted")


@pytest.mark.postgres
def test_postgres_jsonb_advisory_lock_and_atomic_run(settings, configuration):
    """Verify actual PostgreSQL writer exclusion and fresh atomic JSONB persistence."""
    url = os.environ.get("METIS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set METIS_TEST_DATABASE_URL to run actual PostgreSQL gates")
    settings = replace(settings, database_url=url, source_id="test-" + uuid4().hex)
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    with TestClient(app) as client:
        competitor = Database(url, settings.source_id)
        try:
            with pytest.raises(ServiceError, match="Another process"):
                competitor.acquire_writer()
        finally:
            competitor.close()
        key = uuid4().hex
        run = create_run(client, configuration, key)
        started = client.post(
            f"/v1/runs/{run['run_id']}/control",
            json={"action": "start"},
            headers=operator_headers(key + "-start"),
        )
        assert started.status_code == 200, started.text
        final = wait_completed(client, run["run_id"])
        assert final["status"] == "completed" and final["frame_count"] == 27
        with app.state.database.engine.connect() as connection:
            assert (
                len(
                    connection.execute(
                        select(tables.frames.c.payload).where(
                            tables.frames.c.run_id == run["run_id"]
                        )
                    ).all()
                )
                == 27
            )
            assert set(
                connection.execute(
                    select(tables.streams.c.source_id).where(
                        tables.streams.c.run_id == run["run_id"]
                    )
                ).scalars()
            ) == {settings.source_id}
