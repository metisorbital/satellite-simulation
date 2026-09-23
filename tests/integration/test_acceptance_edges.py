"""Acceptance coverage for retention, public transitions, and control expiry."""

from datetime import timedelta
from unittest.mock import Mock

import pytest
from metis_sim.adapters import tables
from metis_sim.adapters.records import utc_now
from metis_sim.adapters.repository import Repository
from metis_sim.application.errors import ServiceError
from metis_sim.application.runner import PendingCommand, Runner
from sqlalchemy import delete, update

from tests.integration.conftest import create_run, operator_headers
from tests.integration.test_service import wait_completed

CONSUMER_HEADERS = {"Authorization": "Bearer " + "c" * 32}


def _start_and_complete(client, run_id: str, key: str) -> dict:
    """Start one short fixture run and wait for its terminal committed state."""
    result = client.post(
        f"/v1/runs/{run_id}/control",
        json={"action": "start"},
        headers=operator_headers(key),
    )
    assert result.status_code == 200, result.text
    completed = wait_completed(client, run_id)
    assert completed["status"] == "completed"
    return completed


def _age_terminal_runs(client, *run_ids: str) -> None:
    """Set terminal wall times beyond the normal cleanup window in the isolated database."""
    with client.app.state.database.writer_transaction() as connection:
        connection.execute(
            update(tables.runs)
            .where(tables.runs.c.run_id.in_(run_ids))
            .values(ended_at=utc_now() - timedelta(days=8))
        )


def test_terminal_retention_expires_old_cursor_and_preserves_retained_run(client, configuration):
    """Expire only unretained terminal history and force an old cursor to resynchronize."""
    expiring = create_run(client, configuration, key="expire")
    _start_and_complete(client, expiring["run_id"], "expire-start")
    expiring_stream = expiring["satellites"][0]["stream_id"]
    first_page = client.get(
        "/v1/telemetry",
        params={"stream_id": expiring_stream, "limit": 1},
        headers=CONSUMER_HEADERS,
    )
    assert first_page.status_code == 200, first_page.text
    cursor = first_page.json()["next_cursor"]

    revision = client.post(
        "/v1/configurations",
        json=configuration,
        headers=operator_headers("retained-config"),
    )
    assert revision.status_code == 201, revision.text
    retained_response = client.post(
        "/v1/runs",
        json={"configuration_id": revision.json()["configuration_id"], "retain": True},
        headers=operator_headers("retained-run"),
    )
    assert retained_response.status_code == 201, retained_response.text
    retained = retained_response.json()
    _start_and_complete(client, retained["run_id"], "retained-start")
    retained_stream = retained["satellites"][0]["stream_id"]

    _age_terminal_runs(client, expiring["run_id"], retained["run_id"])
    assert client.app.state.repository.expire_terminal() == 1

    streams = client.get("/v1/streams", headers=CONSUMER_HEADERS).json()["items"]
    by_id = {stream["stream_id"]: stream for stream in streams}
    assert by_id[expiring_stream]["expired"] is True
    assert by_id[expiring_stream]["first_sequence"] == 0
    assert by_id[expiring_stream]["last_sequence"] == 8
    assert by_id[retained_stream]["expired"] is False

    expired = client.get(
        "/v1/telemetry",
        params={"stream_id": expiring_stream, "after": cursor},
        headers=CONSUMER_HEADERS,
    )
    assert expired.status_code == 410
    assert expired.json()["code"] == "cursor_expired"
    assert expired.json()["details"] == [{"first_sequence": None, "last_sequence": None}]

    retained_page = client.get(
        "/v1/telemetry",
        params={"stream_id": retained_stream},
        headers=CONSUMER_HEADERS,
    )
    assert retained_page.status_code == 200, retained_page.text
    assert [frame["sequence"] for frame in retained_page.json()["items"]] == list(range(9))


def test_cursor_before_partially_retained_history_reports_current_bounds(client, configuration):
    """Require explicit resynchronization when a valid cursor precedes retained frames."""
    run = create_run(client, configuration, key="pruned")
    _start_and_complete(client, run["run_id"], "pruned-start")
    stream_id = run["satellites"][0]["stream_id"]
    first_page = client.get(
        "/v1/telemetry",
        params={"stream_id": stream_id, "limit": 1},
        headers=CONSUMER_HEADERS,
    )
    assert first_page.status_code == 200, first_page.text

    with client.app.state.database.writer_transaction() as connection:
        connection.execute(
            delete(tables.frames).where(
                tables.frames.c.stream_id == stream_id,
                tables.frames.c.sequence < 5,
            )
        )

    expired = client.get(
        "/v1/telemetry",
        params={"stream_id": stream_id, "after": first_page.json()["next_cursor"]},
        headers=CONSUMER_HEADERS,
    )
    assert expired.status_code == 410
    assert expired.json()["code"] == "cursor_expired"
    assert expired.json()["details"] == [{"first_sequence": 5, "last_sequence": 8}]


def test_public_event_sequence_preserves_mode_and_soc_hysteresis(client, configuration):
    """Persist one event per public state transition in stable per-stream order."""
    configuration["satellites"] = [configuration["satellites"][0]]
    configuration["constellations"] = [
        {"constellation_id": "metis-test", "satellite_ids": ["METIS-01"]}
    ]
    configuration["satellites"][0]["operations"] = [{"start_s": 2, "end_s": 4, "mode": "safe"}]
    configuration["profiles"]["leo_power_demo"]["public_limits"] = [
        {
            "channel_id": "eps.battery_soc",
            "operator": "gt",
            "value": 0.84995,
            "clear_value": 0.8499,
        }
    ]
    run = create_run(client, configuration, key="events")
    _start_and_complete(client, run["run_id"], "events-start")
    stream_id = run["satellites"][0]["stream_id"]

    page = client.get("/v1/events", params={"stream_id": stream_id}, headers=CONSUMER_HEADERS)
    assert page.status_code == 200, page.text
    events = page.json()["items"]
    assert [event["event_sequence"] for event in events] == list(range(4))
    assert [event["event_type"] for event in events] == [
        "low_energy_limit_entered",
        "low_energy_limit_cleared",
        "mode_changed",
        "mode_changed",
    ]
    assert events[0]["details"] == {
        "channel_id": "eps.battery_soc",
        "operator": "gt",
        "value": 0.84995,
        "clear_value": 0.8499,
    }
    assert events[1]["details"] == events[0]["details"]
    assert events[2]["details"] == {"from_mode": "nominal", "to_mode": "safe"}
    assert events[3]["details"] == {"from_mode": "safe", "to_mode": "nominal"}


def test_writer_rejects_expired_queued_control_without_late_application():
    """Cancel a stale queued control before it can read or commit a run boundary."""
    repository = Mock(spec=Repository)
    runner = Runner(repository, monotonic=lambda: 6)
    command = PendingCommand("run", "pause", None, ("scope", "key", "hash"), deadline=5)
    runner.commands.put_nowait(command)

    runner._drain_commands()
    with pytest.raises(ServiceError) as failure:
        command.result.result()

    assert failure.value.code == "control_not_applied"
    assert command.phase == "cancelled"
    repository.existing.assert_not_called()
    repository.status.assert_not_called()
    repository.commit.assert_not_called()
    runner._drain_commands()
    repository.status.assert_not_called()
