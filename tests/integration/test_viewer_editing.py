"""Browser constellation revisions and independent reset runs."""

from dataclasses import replace
from datetime import timedelta

import yaml
from fastapi.testclient import TestClient
from metis_sim.adapters import tables
from metis_sim.adapters.records import utc_now
from metis_sim.api.app import create_app
from metis_sim.api.auth import COOKIE
from sqlalchemy import select, update

from tests.integration.conftest import create_run


def test_local_demo_bootstrap_resumes_revised_run(client, configuration):
    """Local editor sessions resume their new run after saving a revision."""
    original = create_run(client, configuration)
    client.app.state.service.demo_run_id = original["run_id"]
    grant = client.get("/v1/viewer/bootstrap").json()
    edited = client.post(
        "/v1/viewer/reset",
        json={},
        headers={
            "Origin": "http://127.0.0.1:8000",
            "X-CSRF-Token": grant["csrf_token"],
            "Idempotency-Key": "local-reset",
        },
    )
    assert edited.status_code == 200, edited.text
    new_id = edited.json()["run"]["run_id"]
    assert new_id != original["run_id"]
    assert client.get("/v1/viewer/bootstrap").json()["run"]["run_id"] == new_id


def test_interactive_viewer_edits_and_resets(settings, configuration, tmp_path):
    """Browser edits create independent runs without exposing private scenario data."""
    path = tmp_path / "template.yaml"
    configuration["scenario"] = []
    path.write_text(yaml.safe_dump(configuration))
    configured = replace(
        settings,
        local_demo=False,
        public_demo=True,
        interactive_public_demo=True,
        cookie_secure=True,
        origins=("https://sim.example",),
        demo_config=path,
    )
    app = create_app(configured, setup_schema=True)
    with TestClient(app, base_url="https://sim.example") as client:
        first = client.get("/v1/viewer/bootstrap")
        assert first.status_code == 200, first.text
        grant = first.json()
        assert "start" in grant["allowed_actions"]
        source_id = grant["run"]["run_id"]
        editable = client.get("/v1/viewer/configuration")
        assert editable.status_code == 200, editable.text
        assert set(editable.json()) == {"satellites"}
        satellites = editable.json()["satellites"]
        assert "scenario" not in str(editable.json())
        satellites[0]["name"] = "Renamed"
        satellites[0]["power"]["panel_area_m2"] = 1.4
        headers = {
            "Origin": "https://sim.example",
            "X-CSRF-Token": grant["csrf_token"],
            "Idempotency-Key": "edit-one",
        }
        edited = client.post(
            "/v1/viewer/configuration", json={"satellites": satellites}, headers=headers
        )
        assert edited.status_code == 200, edited.text
        assert edited.json()["run"]["run_id"] != source_id
        assert edited.json()["run"]["satellites"][0]["name"] == "Renamed"
        assert edited.json()["run"]["satellites"][0]["panel_area_m2"] == 1.4
        assert client.get(f"/v1/runs/{source_id}").status_code == 403
        reset = client.post(
            "/v1/viewer/reset",
            json={},
            headers={
                "Origin": "https://sim.example",
                "X-CSRF-Token": edited.json()["csrf_token"],
                "Idempotency-Key": "reset-one",
            },
        )
        assert reset.status_code == 200, reset.text
        assert reset.json()["run"]["run_id"] != edited.json()["run"]["run_id"]
        assert reset.json()["run"]["committed_tick"] == -1


def test_idle_viewer_slots_are_recovered(settings, configuration, tmp_path):
    """Evicted created browser runs recover from their saved input on return."""
    path = tmp_path / "template.yaml"
    path.write_text(yaml.safe_dump(configuration))
    configured = replace(
        settings,
        local_demo=False,
        public_demo=True,
        interactive_public_demo=True,
        cookie_secure=True,
        origins=("https://sim.example",),
        demo_config=path,
    )
    app = create_app(configured, setup_schema=True)
    with TestClient(app, base_url="https://sim.example") as client:
        first = client.get("/v1/viewer/bootstrap")
        first_run = first.json()["run"]["run_id"]
        first_cookie = first.cookies[COOKIE]
        for _ in range(3):
            client.cookies.clear()
            response = client.get("/v1/viewer/bootstrap")
            assert response.status_code == 200, response.text
        assert first_run not in app.state.runner.prepared
        client.cookies.clear()
        client.cookies.set(COOKIE, first_cookie, domain="sim.example")
        recovered = client.get("/v1/viewer/bootstrap")
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["run"]["run_id"] == first_run
        assert first_run in app.state.runner.prepared
        assert "start" in recovered.json()["allowed_actions"]
        for _ in range(3):
            client.cookies.clear()
            assert client.get("/v1/viewer/bootstrap").status_code == 200
        assert first_run not in app.state.runner.prepared
        client.cookies.clear()
        client.cookies.set(COOKIE, first_cookie, domain="sim.example")
        started = client.post(
            f"/v1/runs/{first_run}/control",
            json={"action": "start"},
            headers={
                "Origin": "https://sim.example",
                "X-CSRF-Token": first.json()["csrf_token"],
                "Idempotency-Key": "start-evicted",
            },
        )
        assert started.status_code == 200, started.text


def test_missing_satellite_id_with_power_is_validation_error(settings, configuration, tmp_path):
    """Malformed power edits return a client error before profile cloning."""
    path = tmp_path / "template.yaml"
    path.write_text(yaml.safe_dump(configuration))
    configured = replace(settings, demo_config=path)
    app = create_app(configured, setup_schema=True)
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        grant = client.get("/v1/viewer/bootstrap").json()
        satellite = client.get("/v1/viewer/configuration").json()["satellites"][0]
        satellite.pop("satellite_id")
        response = client.post(
            "/v1/viewer/configuration",
            json={"satellites": [satellite]},
            headers={
                "Origin": "http://127.0.0.1:8000",
                "X-CSRF-Token": grant["csrf_token"],
                "Idempotency-Key": "malformed-power",
            },
        )
        assert response.status_code == 422, response.text


def test_expired_created_viewer_run_is_pruned(settings, configuration, tmp_path):
    """Expired browser revisions are removed while fresh browser runs survive."""
    path = tmp_path / "template.yaml"
    path.write_text(yaml.safe_dump(configuration))
    configured = replace(
        settings,
        local_demo=False,
        public_demo=True,
        interactive_public_demo=True,
        cookie_secure=True,
        origins=("https://sim.example",),
        demo_config=path,
    )
    app = create_app(configured, setup_schema=True)
    with TestClient(app, base_url="https://sim.example") as client:
        old_run = client.get("/v1/viewer/bootstrap").json()["run"]["run_id"]
        client.cookies.clear()
        fresh_run = client.get("/v1/viewer/bootstrap").json()["run"]["run_id"]
        with app.state.database.writer_transaction() as connection:
            old_config = connection.execute(
                select(tables.runs.c.configuration_id).where(tables.runs.c.run_id == old_run)
            ).scalar_one()
            connection.execute(
                update(tables.configurations)
                .where(tables.configurations.c.configuration_id == old_config)
                .values(created_at=utc_now() - timedelta(hours=5))
            )
        expired = app.state.repository.prune_abandoned_viewer_runs(4 * 3600)
        assert expired == [old_run]
        with app.state.database.engine.connect() as connection:
            assert (
                connection.execute(
                    select(tables.runs.c.run_id).where(tables.runs.c.run_id == old_run)
                ).scalar_one_or_none()
                is None
            )
            assert (
                connection.execute(
                    select(tables.configurations.c.configuration_id).where(
                        tables.configurations.c.configuration_id == old_config
                    )
                ).scalar_one_or_none()
                is None
            )
            assert (
                connection.execute(
                    select(tables.idempotency.c.key).where(
                        tables.idempotency.c.response["run_id"].as_string() == old_run
                    )
                ).first()
                is None
            )
        assert app.state.repository.status(fresh_run)["status"] == "created"
