"""Reproduction across live pacing, pauses, identities and constellation membership."""

import copy
import json
import time
from pathlib import Path

from examples.consumer import accept_frame
from tests.integration.conftest import create_run, operator_headers
from tests.integration.test_service import wait_completed


def test_actual_pacing_and_pause_do_not_change_physics(client, configuration):
    """Preserve canonical traces across pacing, pauses, and constellation growth."""
    configuration["run"]["duration_s"] = 3
    configuration["satellites"][0]["operations"] = [
        {"start_s": 1, "end_s": 3, "mode": "payload_active"}
    ]
    traces, streams = [], []
    for index, speed in enumerate([1, 5, 20, 20]):
        candidate = copy.deepcopy(configuration)
        candidate["run"]["speed"] = speed
        if index == 3:
            satellite = copy.deepcopy(candidate["satellites"][0])
            satellite["satellite_id"] = "METIS-04"
            satellite["name"] = "Fourth spacecraft"
            candidate["satellites"].append(satellite)
            candidate["constellations"][0]["satellite_ids"].append("METIS-04")
        run = create_run(client, candidate, key=f"run-{index}")
        control = f"/v1/runs/{run['run_id']}/control"
        client.post(control, json={"action": "start"}, headers=operator_headers(f"start-{index}"))
        if speed == 1:
            time.sleep(0.03)
            assert (
                client.post(
                    control, json={"action": "pause"}, headers=operator_headers("pause")
                ).status_code
                == 200
            )
            time.sleep(0.02)
            assert (
                client.post(
                    control, json={"action": "resume"}, headers=operator_headers("resume")
                ).status_code
                == 200
            )
        assert wait_completed(client, run["run_id"])["status"] == "completed"
        frames = client.app.state.reader.snapshot(run["run_id"], history=41)["frames"]
        traces.append(
            sorted(
                [
                    {
                        name: frame[name]
                        for name in [
                            "satellite_id",
                            "sequence",
                            "observed_at",
                            "sample_window_s",
                            "mode",
                            "interval_mode",
                            "channels",
                        ]
                    }
                    for frame in frames
                    if frame["satellite_id"] != "METIS-04"
                ],
                key=lambda frame: (frame["satellite_id"], frame["sequence"]),
            )
        )
        streams.append({frame["stream_id"] for frame in frames})
    assert all(trace == traces[0] for trace in traces[1:])
    assert all(
        not left & right for index, left in enumerate(streams) for right in streams[index + 1 :]
    )


def test_consumer_accepts_observed_and_synthetic_without_simulator_identity(client, configuration):
    """Deduplicate both producer kinds using only the public stream identity."""
    candidates = list(Path("tests/contracts").rglob("*observed*.json"))
    assert candidates, "An observed producer contract fixture must be committed"
    observed = json.loads(candidates[0].read_text())
    seen = set()
    assert "run_id" not in observed
    assert accept_frame(observed, seen)
    assert not accept_frame(observed, seen)
    run = create_run(client, configuration)
    client.post(
        f"/v1/runs/{run['run_id']}/control",
        json={"action": "start"},
        headers=operator_headers("start"),
    )
    wait_completed(client, run["run_id"])
    frame = client.app.state.reader.snapshot(run["run_id"])["frames"][0]
    assert accept_frame(frame, seen)
    assert not accept_frame(frame, seen)
