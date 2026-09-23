"""Bound database reads independently of the number of immutable batch records."""

import os
from dataclasses import replace
from operator import itemgetter
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from metis_sim.api.app import create_app
from sqlalchemy import event

from tests.integration.conftest import create_run


@pytest.mark.parametrize("postgres", [False, True], ids=["sqlite", "postgres"])
def test_fresh_inserts_and_retries_use_bounded_collision_reads(settings, configuration, postgres):
    """Avoid a per-row SELECT while preserving frozen identities on complete retry."""
    if postgres:
        url = os.environ.get("METIS_TEST_DATABASE_URL")
        if not url:
            pytest.skip("Set METIS_TEST_DATABASE_URL for the production driver gate")
        settings = replace(settings, database_url=url, source_id=uuid4().hex)
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    with TestClient(app) as client:
        state = create_run(client, configuration, uuid4().hex)
        prepared = app.state.runner.prepared[state["run_id"]]
        frames, events, truth = [], [], []
        for tick in range(4):
            f, e, t = prepared.projector.project(prepared.engine.sample(tick))
            frames.extend(f)
            events.extend(e)
            truth.extend(t)
        state.update(
            status="paused",
            committed_tick=3,
            committed_at=frames[-1]["observed_at"],
            frame_count=len(frames),
        )
        collision_reads = []

        def record_read(connection, cursor, statement, parameters, context, executemany):
            """Record only collision-verification SQL, never its parameters."""
            if statement.startswith("SELECT") and "payload_hash" in statement:
                collision_reads.append(statement)

        event.listen(app.state.database.engine, "after_cursor_execute", record_read)
        try:
            app.state.repository.commit(state, frames, events, truth)
            assert collision_reads == []
            app.state.repository.commit(state, frames, events, truth)
            assert 1 <= len(collision_reads) <= 3  # One read per nonempty log table.
        finally:
            event.remove(app.state.database.engine, "after_cursor_execute", record_read)
        persisted = app.state.reader.snapshot(state["run_id"], history=41)["frames"]
        identity = itemgetter("stream_id", "sequence")
        assert sorted(persisted, key=identity) == sorted(frames, key=identity)
