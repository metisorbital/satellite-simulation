"""Isolated service fixtures using the real numerical engine and SQL adapter."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from metis_sim.api.app import create_app
from metis_sim.settings import Settings


@pytest.fixture
def configuration():
    """Return a short real orbital run without scheduled faults."""
    value = yaml.safe_load(Path("configs/demo.yaml").read_text())
    value["run"]["duration_s"] = 8
    value["run"]["speed"] = 20
    value["scenario"] = []
    for satellite in value["satellites"]:
        satellite["operations"] = []
    return value


@pytest.fixture
def settings(tmp_path):
    """Return independent database and authentication settings for one test."""
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.sqlite'}",
        session_secret="s" * 40,
        operator_token="o" * 32,
        consumer_token="c" * 32,
        evaluator_token="e" * 32,
        local_demo=True,
        frontend_path=tmp_path / "no-ui",
    )


@pytest.fixture
def client(settings):
    """Yield a fully initialized application and real writer thread."""
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url="http://127.0.0.1:8000") as connection:
        yield connection


def operator_headers(key: str) -> dict[str, str]:
    """Build an operator credential and a distinct mutation identity."""
    return {"Authorization": "Bearer " + "o" * 32, "Idempotency-Key": key}


def create_run(client, configuration, key="run"):
    """Create an independent run through the public operator endpoints."""
    revision = client.post(
        "/v1/configurations", json=configuration, headers=operator_headers(key + "-config")
    )
    assert revision.status_code == 201, revision.text
    result = client.post(
        "/v1/runs",
        json={"configuration_id": revision.json()["configuration_id"]},
        headers=operator_headers(key),
    )
    assert result.status_code == 201, result.text
    return result.json()
