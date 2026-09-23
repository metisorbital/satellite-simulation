"""End-to-end controls, durable replay, idempotency and access isolation."""

import copy
import json
import time

import pytest
from metis_sim.application.errors import ServiceError

from tests.integration.conftest import create_run, operator_headers


def wait_completed(client, run_id):
    """Wait a bounded wall interval for the short physical fixture."""
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        state = client.get(f"/v1/runs/{run_id}", headers=operator_headers("read")).json()
        if state["status"] in {"completed", "failed"}:
            return state
        time.sleep(0.03)
    pytest.fail("Run did not complete within five wall seconds")


def test_immutable_replay_idempotency_and_public_private_separation(client, configuration):
    """Replay immutable public outputs while protecting private evaluation records."""
    run = create_run(client, configuration)
    run_id = run["run_id"]
    control = f"/v1/runs/{run_id}/control"
    initial = client.post(control, json={"action": "start"}, headers=operator_headers("start"))
    assert initial.status_code == 200, initial.text
    completed = wait_completed(client, run_id)
    assert completed["status"] == "completed"
    assert completed["committed_tick"] == 8
    assert completed["frame_count"] == 27
    retry = client.post(control, json={"action": "start"}, headers=operator_headers("start"))
    assert retry.json() == initial.json()
    assert (
        client.post(
            control, json={"action": "pause"}, headers=operator_headers("start")
        ).status_code
        == 409
    )
    consumer = {"Authorization": "Bearer " + "c" * 32}
    stream = run["satellites"][0]["stream_id"]
    first = client.get(
        "/v1/telemetry", params={"stream_id": stream, "limit": 4}, headers=consumer
    ).json()
    second = client.get(
        "/v1/telemetry",
        params={"stream_id": stream, "after": first["next_cursor"]},
        headers=consumer,
    ).json()
    assert [frame["sequence"] for frame in first["items"] + second["items"]] == list(range(9))
    replay = client.get(
        "/v1/telemetry", params={"stream_id": stream, "limit": 4}, headers=consumer
    ).json()
    assert replay["items"] == first["items"]
    assert (
        client.get(
            "/v1/events",
            params={"stream_id": stream, "after": first["next_cursor"]},
            headers=consumer,
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/v1/telemetry",
            params={"stream_id": run["satellites"][1]["stream_id"], "after": first["next_cursor"]},
            headers=consumer,
        ).status_code
        == 422
    )
    empty = client.get(
        "/v1/telemetry", params={"stream_id": stream, "after": "latest"}, headers=consumer
    ).json()
    again = client.get(
        "/v1/telemetry",
        params={"stream_id": stream, "after": empty["next_cursor"]},
        headers=consumer,
    ).json()
    assert empty["items"] == [] and again["next_cursor"] == empty["next_cursor"]
    public = json.dumps([run, first, second])
    assert all(
        secret not in public
        for secret in [
            "hidden_derating",
            "root_seed",
            "reserve_soc",
            "scenario",
            "configuration_hash",
        ]
    )
    assert client.get(f"/v1/evaluation/runs/{run_id}/truth", headers=consumer).status_code == 403
    assert client.get(f"/v1/operator/runs/{run_id}/manifest", headers=consumer).status_code == 403
    truth = client.get(
        f"/v1/evaluation/runs/{run_id}/truth", headers={"Authorization": "Bearer " + "e" * 32}
    ).json()
    endings = [item for item in truth["items"] if item["terminal_reason"]]
    assert len(endings) == 3
    assert all(
        item["right_censored"]
        and item["terminal_reason"] == "duration_reached"
        and item["tick"] == 8
        for item in endings
    )


def test_viewer_run_scope_csrf_snapshot_and_visual_socket(client, configuration):
    """Enforce the viewer capability across controls, snapshots, and visual delivery."""
    run = create_run(client, configuration)
    run_id = run["run_id"]
    client.app.state.service.demo_run_id = run_id
    bootstrap = client.get("/v1/viewer/bootstrap")
    assert bootstrap.status_code == 200
    assert "HttpOnly" in bootstrap.headers["set-cookie"]
    control = f"/v1/runs/{run_id}/control"
    headers = {
        "Idempotency-Key": "viewer-start",
        "X-CSRF-Token": bootstrap.json()["csrf_token"],
        "Origin": "http://127.0.0.1:8000",
    }
    assert (
        client.post(
            control, json={"action": "start"}, headers={"Idempotency-Key": "no-csrf"}
        ).status_code
        == 403
    )
    assert client.post(control, json={"action": "start"}, headers=headers).status_code == 200
    wait_completed(client, run_id)
    assert client.get("/v1/runs/another-run").status_code == 403
    assert client.post("/v1/configurations", json=configuration, headers=headers).status_code == 403
    assert client.get(f"/v1/operator/runs/{run_id}/manifest").status_code == 403
    snapshot = client.get(f"/v1/runs/{run_id}/snapshot?history=41")
    assert snapshot.status_code == 200, snapshot.text
    assert len(snapshot.json()["frames"]) == 27
    assert (
        client.get(f"/v1/runs/{run_id}/snapshot", params={"at": "2026-09-21T00:00:09Z"}).status_code
        == 422
    )
    with client.websocket_connect(
        f"ws://127.0.0.1:8000/v1/runs/{run_id}/visual", headers={"Origin": "http://127.0.0.1:8000"}
    ) as websocket:
        payload = websocket.receive_json()
        assert payload["type"] == "snapshot"
        assert payload["status"]["committed_tick"] == 8
        assert "hidden_derating" not in json.dumps(payload)


def test_conflicting_identity_rolls_back_entire_batch(client, configuration):
    """Reject changed content under an existing identity without partial writes."""
    run = create_run(client, configuration)
    run_id = run["run_id"]
    client.post(
        f"/v1/runs/{run_id}/control", json={"action": "start"}, headers=operator_headers("start")
    )
    final = wait_completed(client, run_id)
    snapshot = client.app.state.reader.snapshot(run_id)
    frame = copy.deepcopy(snapshot["frames"][0])
    repository = client.app.state.repository
    assert repository.commit(final, [frame], [], []) == final
    frame["channels"]["eps.battery_soc"]["value"] = 0.123
    with pytest.raises(ServiceError, match="conflicting content"):
        repository.commit(final, [frame], [], [])
    assert client.app.state.reader.snapshot(run_id)["frames"] == snapshot["frames"]


def test_pause_boundary_and_idempotent_resume(client, configuration):
    """Keep a paused committed boundary fixed and acknowledge resume retries once."""
    configuration["run"]["duration_s"] = 100
    run = create_run(client, configuration)
    control = f"/v1/runs/{run['run_id']}/control"
    client.post(control, json={"action": "start"}, headers=operator_headers("start"))
    time.sleep(0.08)
    pause = client.post(control, json={"action": "pause"}, headers=operator_headers("pause"))
    assert pause.status_code == 200, pause.text
    tick = pause.json()["committed_tick"]
    time.sleep(0.1)
    assert (
        client.get(f"/v1/runs/{run['run_id']}", headers=operator_headers("read")).json()[
            "committed_tick"
        ]
        == tick
    )
    assert (
        client.post(control, json={"action": "pause"}, headers=operator_headers("pause2")).json()[
            "committed_tick"
        ]
        == tick
    )
    assert (
        client.post(
            control, json={"action": "resume"}, headers=operator_headers("resume")
        ).status_code
        == 200
    )
    stop = client.post(control, json={"action": "stop"}, headers=operator_headers("stop"))
    assert stop.status_code == 200 and stop.json()["status"] == "stopped"
