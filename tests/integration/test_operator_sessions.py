"""Demo operator identity, cookie lifecycle, isolation, and private persistence."""

import json
from dataclasses import replace
from datetime import timedelta
from http.cookies import SimpleCookie
from importlib.resources import files

import pytest
import yaml
from fastapi.testclient import TestClient
from metis_sim.adapters import tables
from metis_sim.adapters.records import utc_now
from metis_sim.api.app import create_app
from metis_sim.api.auth import COOKIE
from sqlalchemy import func, select, update

ORIGIN = "http://127.0.0.1:8000"


@pytest.fixture
def operator_client(settings, configuration, tmp_path):
    """Yield a local demo with a small template and no anonymous prepared run.

    Parameters
    ----------
    settings : Settings
        Isolated database and credentials.
    configuration : dict
        Short validated physical configuration.
    tmp_path : Path
        Directory for the demo template.

    Yields
    ------
    TestClient
        Running API with a real writer and database.
    """
    configuration["run"]["speed"] = 1
    path = tmp_path / "operators.yaml"
    path.write_text(yaml.safe_dump(configuration))
    app = create_app(replace(settings, demo_config=path), setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url=ORIGIN) as client:
        yield client


def _login(client, login="operator1", password="any-demo-password"):
    response = client.post(
        "/v1/viewer/login",
        json={"login": login, "password": password},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _headers(grant, key="test"):
    return {
        "Origin": ORIGIN,
        "X-CSRF-Token": grant["csrf_token"],
        "Idempotency-Key": key,
    }


def _cookie(client, cookie):
    client.cookies.clear()
    client.cookies.set(COOKIE, cookie, domain="127.0.0.1")


def _run_count(client):
    with client.app.state.database.engine.connect() as connection:
        return connection.execute(select(func.count()).select_from(tables.runs)).scalar_one()


def test_first_visit_and_login_preserve_private_identity(operator_client, caplog):
    """Sign-in persists the directory UUID and reload resumes exactly one run.

    Notes
    -----
    Session reads cannot silently allocate anonymous runs. Neither responses,
    logs, nor any persisted JSON may contain the entered password.
    """
    client = operator_client
    assert client.get("/v1/viewer/session").status_code == 401
    assert _run_count(client) == 0
    password = "transient-only-password-value"
    grant = _login(client, "  OPERATOR1  ", password)
    directory = json.loads(files("metis_sim").joinpath("data/mock_operators.json").read_text())
    assert grant["operator"] == directory[0]
    run_id = grant["run"]["run_id"]
    assert grant["run"]["status"] == "created"
    assert "start" in grant["allowed_actions"]
    assert client.get("/v1/viewer/session").json() == grant
    assert client.get("/v1/viewer/bootstrap").json() == grant
    assert _login(client, password="a-different-unverified-password") == grant
    assert _run_count(client) == 1
    with client.app.state.database.engine.connect() as connection:
        row = connection.execute(select(tables.runs)).mappings().one()
        assert row["user_id"] == directory[0]["user_id"]
        stored = {
            table.name: [dict(item) for item in connection.execute(select(table)).mappings()]
            for table in (tables.runs, tables.configurations, tables.idempotency)
        }
    assert password not in json.dumps(stored, default=str)
    assert password not in caplog.text
    for path in (f"/v1/runs/{run_id}", f"/v1/runs/{run_id}/snapshot", "/v1/streams"):
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert "user_id" not in response.text
        assert "operator1" not in response.text
    assert (
        client.post(
            "/v1/viewer/login",
            json={"login": "operator2", "password": "demo"},
            headers={"Origin": ORIGIN},
        ).status_code
        == 409
    )
    assert _run_count(client) == 1


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"login": "unknown", "password": "demo"}, 401),
        ({"login": "operator1", "password": ""}, 422),
        ({"login": "", "password": "demo"}, 422),
        ({"login": "operator1"}, 422),
        ({"login": "operator1", "password": 42}, 422),
        ({"login": "operator1", "password": "demo", "user_id": "override"}, 422),
    ],
)
def test_invalid_login_never_allocates_a_run(operator_client, body, status):
    """Reject malformed or unknown input before private run creation.

    Parameters
    ----------
    operator_client : TestClient
        Empty local demo service.
    body : dict
        Invalid login input.
    status : int
        Expected client error status.
    """
    response = operator_client.post("/v1/viewer/login", json=body, headers={"Origin": ORIGIN})
    assert response.status_code == status, response.text
    assert _run_count(operator_client) == 0
    assert operator_client.get("/v1/viewer/session").status_code == 401


def test_operators_are_run_scoped_and_reset_preserves_identity(operator_client):
    """Separate operators cannot inspect or control each other's runs.

    Notes
    -----
    Both constellation edits and resets allocate new runs with the same
    private operator identity and keep the signed browser identity intact.
    """
    client = operator_client
    first = _login(client)
    first_cookie = client.cookies[COOKIE]
    first_id = first["run"]["run_id"]
    client.cookies.clear()
    second = _login(client, "operator2", "anything")
    second_id = second["run"]["run_id"]
    assert first_id != second_id
    assert first["operator"]["user_id"] != second["operator"]["user_id"]
    assert client.get(f"/v1/runs/{first_id}").status_code == 403
    assert (
        client.post(
            f"/v1/runs/{first_id}/control",
            json={"action": "start"},
            headers=_headers(second),
        ).status_code
        == 403
    )
    assert {item["run_id"] for item in client.get("/v1/streams").json()["items"]} == {second_id}
    _cookie(client, first_cookie)
    assert client.get(f"/v1/runs/{second_id}").status_code == 403
    satellites = client.get("/v1/viewer/configuration").json()["satellites"]
    satellites[0]["name"] = "Operator one satellite"
    edited = client.post(
        "/v1/viewer/configuration",
        json={"satellites": satellites},
        headers=_headers(first, "operator-edit"),
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["operator"] == first["operator"]
    reset = client.post(
        "/v1/viewer/reset", json={}, headers=_headers(edited.json(), "operator-reset")
    )
    assert reset.status_code == 200, reset.text
    assert reset.json()["operator"] == first["operator"]
    for grant in (first, edited.json(), reset.json()):
        run = client.app.state.repository.private_run(grant["run"]["run_id"])
        assert run["user_id"] == first["operator"]["user_id"]
    assert client.get("/v1/viewer/session").json() == reset.json()
    assert client.get("/v1/viewer/bootstrap").json() == reset.json()


def test_login_and_logout_enforce_origin_and_csrf(operator_client):
    """Untrusted origins and missing tokens cannot change an operator session.

    Notes
    -----
    Successful logout clears the cookie while retaining its created run and
    private identity, and a repeated logout remains harmless.
    """
    client = operator_client
    for headers in ({}, {"Origin": "https://untrusted.example"}):
        response = client.post(
            "/v1/viewer/login", json={"login": "operator1", "password": "demo"}, headers=headers
        )
        assert response.status_code == 403
    assert _run_count(client) == 0
    grant = _login(client)
    for headers in (
        {"Origin": ORIGIN},
        {"Origin": "https://untrusted.example", "X-CSRF-Token": grant["csrf_token"]},
    ):
        assert client.post("/v1/viewer/logout", json={}, headers=headers).status_code == 403
        assert client.get("/v1/viewer/session").json() == grant
    assert (
        client.post(
            "/v1/viewer/logout", json={"run_id": "override"}, headers=_headers(grant)
        ).status_code
        == 422
    )
    logout = client.post("/v1/viewer/logout", json={}, headers=_headers(grant))
    assert logout.status_code == 200
    assert logout.json() == {}
    assert "HttpOnly" in logout.headers["set-cookie"]
    assert "SameSite=strict" in logout.headers["set-cookie"]
    assert client.get("/v1/viewer/session").status_code == 401
    run = client.app.state.repository.private_run(grant["run"]["run_id"])
    assert run["status"] == "created"
    assert run["user_id"] == grant["operator"]["user_id"]
    assert client.post("/v1/viewer/logout", json={}, headers={"Origin": ORIGIN}).status_code == 200


def test_logout_stops_only_the_owning_operators_active_run(operator_client):
    """Logout frees the single active slot without changing another operator's run.

    Notes
    -----
    The stop is durably applied only after successful CSRF validation.
    """
    client = operator_client
    first = _login(client)
    first_id = first["run"]["run_id"]
    first_cookie = client.cookies[COOKIE]
    for action in ("start", "pause"):
        result = client.post(
            f"/v1/runs/{first_id}/control", json={"action": action}, headers=_headers(first, action)
        )
        assert result.status_code == 200, result.text
    assert client.post("/v1/viewer/logout", json={}, headers={"Origin": ORIGIN}).status_code == 403
    assert client.app.state.repository.status(first_id)["status"] == "paused"
    client.cookies.clear()
    second = _login(client, "operator2")
    assert client.post("/v1/viewer/logout", json={}, headers=_headers(second)).status_code == 200
    assert client.app.state.repository.status(first_id)["status"] == "paused"
    _cookie(client, first_cookie)
    assert client.post("/v1/viewer/logout", json={}, headers=_headers(first)).status_code == 200
    run = client.app.state.repository.private_run(first_id)
    assert run["status"] == "stopped"
    assert run["user_id"] == first["operator"]["user_id"]
    second = _login(client, "operator2")
    started = client.post(
        f"/v1/runs/{second['run']['run_id']}/control",
        json={"action": "start"},
        headers=_headers(second, "start-next"),
    )
    assert started.status_code == 200, started.text


@pytest.mark.parametrize("interactive", [False, True])
def test_hosted_login_preserves_explicit_demo_mode(settings, configuration, tmp_path, interactive):
    """Only explicitly interactive HTTPS deployments permit mock login.

    Parameters
    ----------
    settings : Settings
        Isolated credentials and database.
    configuration : dict
        Small physical configuration template.
    tmp_path : Path
        Template directory.
    interactive : bool
        Whether this deployment permits interactive browser sessions.
    """
    path = tmp_path / "hosted.yaml"
    path.write_text(yaml.safe_dump(configuration))
    hosted = replace(
        settings,
        local_demo=False,
        public_demo=True,
        interactive_public_demo=interactive,
        cookie_secure=True,
        origins=("https://sim.example",),
        demo_config=path,
    )
    app = create_app(hosted, setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url="https://sim.example") as client:
        response = client.post(
            "/v1/viewer/login",
            json={"login": "operator3", "password": "any"},
            headers={"Origin": "https://sim.example"},
        )
        assert response.status_code == (200 if interactive else 403), response.text
        if interactive:
            assert "Secure" in response.headers["set-cookie"]
            assert response.json()["operator"]["login"] == "operator3"
        else:
            assert _run_count(client) == 0
            assert client.get("/v1/viewer/session").status_code == 401


def test_legacy_viewer_grants_are_not_mock_logins(operator_client):
    """Anonymous legacy grants still work but never bypass the new login view.

    Notes
    -----
    A legacy cookie has no operator claim or private run user ID.
    """
    client = operator_client
    run = client.app.state.service.create_viewer_template_run(client.app.state.settings.demo_config)
    client.app.state.service.demo_run_id = run["run_id"]
    legacy = client.get("/v1/viewer/bootstrap")
    assert legacy.status_code == 200, legacy.text
    assert legacy.json()["operator"] is None
    assert client.get("/v1/viewer/session").status_code == 401
    assert client.app.state.repository.private_run(run["run_id"])["user_id"] is None
    assert client.get(f"/v1/runs/{run['run_id']}").status_code == 200
    client.cookies.clear()
    assert (
        client.get(
            "/v1/viewer/session", headers={"Authorization": "Bearer " + "o" * 32}
        ).status_code
        == 401
    )


@pytest.mark.parametrize("action", ["login", "switch", "logout"])
def test_stale_run_cookie_can_login_again_or_logout(operator_client, action):
    """A pruned run cannot trap its still-signed cookie in a failed-login loop.

    Parameters
    ----------
    operator_client : TestClient
        Isolated local demo service.
    action : str
        Session action to attempt after retention removes its old run.
    """
    client = operator_client
    grant = _login(client)
    run_id = grant["run"]["run_id"]
    with client.app.state.database.writer_transaction() as connection:
        configuration_id = connection.execute(
            select(tables.runs.c.configuration_id).where(tables.runs.c.run_id == run_id)
        ).scalar_one()
        connection.execute(
            update(tables.configurations)
            .where(tables.configurations.c.configuration_id == configuration_id)
            .values(created_at=utc_now() - timedelta(hours=5))
        )
    client.app.state.service.create_viewer_template_run(client.app.state.settings.demo_config)
    assert client.get("/v1/viewer/session").status_code == 401
    if action != "logout":
        replacement = _login(client, "operator2" if action == "switch" else "operator1")
        assert replacement["run"]["run_id"] != run_id
        assert (replacement["operator"] == grant["operator"]) == (action == "login")
        assert client.get("/v1/viewer/session").json() == replacement
    else:
        response = client.post("/v1/viewer/logout", json={}, headers=_headers(grant))
        assert response.status_code == 200, response.text
        assert client.get("/v1/viewer/session").status_code == 401


def test_expired_operator_run_is_reclaimed_before_next_login(operator_client, monkeypatch):
    """An expired paused demo session cannot monopolize the single active slot.

    Notes
    -----
    Advancing the injected wall clock replaces sleeping. Cleanup preserves
    private ownership and runs through the normal durable stop command.
    """
    from types import SimpleNamespace

    client = operator_client
    first = _login(client)
    run_id = first["run"]["run_id"]
    for action in ("start", "pause"):
        response = client.post(
            f"/v1/runs/{run_id}/control",
            json={"action": action},
            headers=_headers(first, action),
        )
        assert response.status_code == 200, response.text
    private = client.app.state.repository.private_run(run_id)
    expires_at = private["manifest"]["viewer_expires_at"]
    claims = client.app.state.auth.serializer.loads(client.cookies[COOKIE])
    assert claims["expires_at"] == expires_at
    assert "viewer_expires_at" not in json.dumps(first)
    clock = SimpleNamespace(time=lambda: expires_at + 1)
    for module in ("api.auth", "api.routes", "application.service"):
        monkeypatch.setattr(f"metis_sim.{module}.time", clock)
    assert client.get("/v1/viewer/session").status_code == 401
    assert client.post("/v1/viewer/logout", json={}, headers=_headers(first)).status_code == 200
    replacement = _login(client, "operator2")
    stopped = client.app.state.repository.private_run(run_id)
    assert stopped["status"] == "stopped"
    assert stopped["user_id"] == first["operator"]["user_id"]
    assert stopped["public_status"]["frame_count"] >= 3
    response = client.post(
        f"/v1/runs/{replacement['run']['run_id']}/control",
        json={"action": "start"},
        headers=_headers(replacement, "replacement-start"),
    )
    assert response.status_code == 200, response.text


def test_mock_login_never_reclaims_legacy_active_run(operator_client, monkeypatch):
    """Lease cleanup excludes anonymous or bearer-created legacy runs.

    Notes
    -----
    The existing single-active-run conflict remains applicable while another
    authorized, unexpired run owns the simulation writer.
    """
    from types import SimpleNamespace

    client = operator_client
    run_id = client.app.state.service.prepare_demo(client.app.state.settings.demo_config)
    legacy = client.get("/v1/viewer/bootstrap").json()
    for action in ("start", "pause"):
        response = client.post(
            f"/v1/runs/{run_id}/control",
            json={"action": action},
            headers=_headers(legacy, action),
        )
        assert response.status_code == 200, response.text
    monkeypatch.setattr(
        "metis_sim.application.service.time", SimpleNamespace(time=lambda: 9_999_999_999)
    )
    client.cookies.clear()
    grant = _login(client)
    assert client.app.state.repository.status(run_id)["status"] == "paused"
    assert (
        client.post(
            f"/v1/runs/{grant['run']['run_id']}/control",
            json={"action": "start"},
            headers=_headers(grant, "separate-start"),
        ).status_code
        == 409
    )


def test_reset_cookie_uses_durable_lease_on_idempotent_retry(operator_client, monkeypatch):
    """A retry cannot extend a signed session past its stored run lease.

    Notes
    -----
    A new reset renews the lease, while replaying its saved acknowledgement
    retains that same expiry even if the later request's clock has advanced.
    """
    from types import SimpleNamespace

    client = operator_client
    first = _login(client)
    source_cookie = client.cookies[COOKIE]
    first_expiry = client.app.state.auth.serializer.loads(source_cookie)["expires_at"]
    now = first_expiry - client.app.state.settings.session_lifetime_s + 30
    monkeypatch.setattr("metis_sim.api.routes.time", SimpleNamespace(time=lambda: now))
    reset = client.post("/v1/viewer/reset", json={}, headers=_headers(first, "same-reset"))
    assert reset.status_code == 200, reset.text
    reset_expiry = client.app.state.auth.serializer.loads(client.cookies[COOKIE])["expires_at"]
    assert reset_expiry > first_expiry
    run_id = reset.json()["run"]["run_id"]
    assert (
        client.app.state.repository.private_run(run_id)["manifest"]["viewer_expires_at"]
        == reset_expiry
    )
    monkeypatch.setattr("metis_sim.api.routes.time", SimpleNamespace(time=lambda: now + 30))
    _cookie(client, source_cookie)
    retry = client.post("/v1/viewer/reset", json={}, headers=_headers(first, "same-reset"))
    assert retry.status_code == 200, retry.text
    assert retry.json()["run"]["run_id"] == run_id
    assert (
        client.app.state.auth.serializer.loads(client.cookies[COOKIE])["expires_at"] == reset_expiry
    )
    cookie = SimpleCookie()
    cookie.load(retry.headers["set-cookie"])
    assert int(cookie[COOKIE]["max-age"]) == max(0, int(reset_expiry - (now + 30)))
