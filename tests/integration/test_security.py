"""Negative access checks at HTTP and WebSocket trust boundaries."""

import threading
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from metis_sim.adapters import tables
from metis_sim.api.app import create_app
from metis_sim.api.auth import COOKIE
from sqlalchemy import func, select
from starlette.websockets import WebSocketDisconnect

from tests.integration.conftest import create_run, operator_headers

ORIGIN = "http://127.0.0.1:8000"


def _issue_viewer(client, run_id, key="session"):
    response = client.post(
        f"/v1/operator/runs/{run_id}/viewer-session", json={}, headers=operator_headers(key)
    )
    assert response.status_code == 200, response.text
    return response


def test_non_ascii_bearer_returns_unauthorized(client):
    """Treat malformed credential bytes as failed authentication."""
    response = client.get("/v1/catalog", headers=[(b"authorization", b"Bearer \xff")])
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_non_ascii_csrf_returns_forbidden_without_mutation(client, configuration):
    """Reject malformed CSRF bytes before the command reaches the writer."""
    run = create_run(client, configuration)
    _issue_viewer(client, run["run_id"])
    response = client.post(
        f"/v1/runs/{run['run_id']}/control",
        json={"action": "start"},
        headers=[
            (b"origin", ORIGIN.encode()),
            (b"x-csrf-token", b"\xff"),
            (b"idempotency-key", b"invalid-csrf"),
        ],
    )
    assert response.status_code == 403
    assert response.json()["code"] == "csrf_failed"
    assert client.app.state.repository.status(run["run_id"])["status"] == "created"


@pytest.mark.parametrize("local_bootstrap", [False, True])
def test_https_issuance_always_sets_secure_cookie(settings, configuration, local_bootstrap):
    """Protect both browser-session issuance routes when HTTPS is active."""
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url="https://127.0.0.1:8000") as client:
        run = create_run(client, configuration)
        if local_bootstrap:
            app.state.service.demo_run_id = run["run_id"]
            response = client.get("/v1/viewer/bootstrap")
        else:
            response = _issue_viewer(client, run["run_id"])
        assert response.status_code == 200
        cookie = response.headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "; Secure" in cookie


@pytest.mark.parametrize("encoding", ["json", "yaml"])
@pytest.mark.parametrize("route", ["/v1/configurations", "/v1/configurations/validate"])
def test_deep_configuration_returns_bounded_error(client, encoding, route):
    """Reject excessive parser recursion without a traceback or payload echo."""
    nested = "[" * 2000 + '"PRIVATE_INPUT_SENTINEL"' + "]" * 2000
    body = '{"unexpected":' + nested + "}" if encoding == "json" else "unexpected: " + nested
    response = client.post(
        route,
        content=body,
        headers={**operator_headers("deep"), "Content-Type": f"application/{encoding}"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_configuration"
    assert "PRIVATE_INPUT_SENTINEL" not in response.text


@pytest.mark.parametrize("invalid_projection", [False, True])
def test_unexpected_http_error_has_redacted_envelope(
    client, configuration, monkeypatch, caplog, invalid_projection
):
    """Contain an unexpected dependency failure before responses and server logs."""
    run = create_run(client, configuration)

    def unavailable(_run_id):
        if invalid_projection:
            return {**run, "private_scenario": "PRIVATE_ERROR_SENTINEL"}
        raise RuntimeError("PRIVATE_ERROR_SENTINEL")

    monkeypatch.setattr(client.app.state.repository, "status", unavailable)
    # The shared fixture already owns this app's lifespan and writer thread.
    isolated_transport = TestClient(client.app, base_url=ORIGIN, raise_server_exceptions=False)
    try:
        response = isolated_transport.get(
            f"/v1/runs/{run['run_id']}", headers=operator_headers("read")
        )
    finally:
        isolated_transport.close()
    assert response.status_code == 500
    assert response.json() == {
        "code": "internal_error",
        "message": "An unexpected service error occurred.",
        "details": [],
        "request_id": response.headers["x-request-id"],
    }
    assert response.headers["cache-control"] == "no-store"
    assert "PRIVATE_ERROR_SENTINEL" not in response.text + caplog.text


def test_request_size_is_bounded_before_configuration_parsing(client):
    """Reject an oversized request without invoking either configuration parser."""
    response = client.post(
        "/v1/configurations/validate", content=b" " * 1_048_577, headers=operator_headers("large")
    )
    assert response.status_code == 422
    assert response.json()["code"] == "request_too_large"


def test_visual_expiry_preempts_slow_snapshot(client, configuration, monkeypatch):
    """Close an active session before a slow read can deliver post-expiry data."""
    run = create_run(client, configuration)
    context = client.app.state
    cookie, _ = context.auth.issue(run["run_id"])
    claims = context.auth.serializer.loads(cookie)
    original = context.reader.snapshot
    finished = threading.Event()

    def slow_snapshot(*args):
        try:
            time.sleep(0.4)
            return original(*args)
        finally:
            finished.set()

    monkeypatch.setattr(context.reader, "snapshot", slow_snapshot)
    claims["expires_at"] = time.time() + 0.2
    client.cookies.set(COOKIE, context.auth.serializer.dumps(claims))
    with client.websocket_connect(
        f"ws://127.0.0.1:8000/v1/runs/{run['run_id']}/visual", headers={"Origin": ORIGIN}
    ) as socket:
        message = socket.receive()
        assert message["type"] == "websocket.close"
        assert message["code"] == 1008
    assert finished.wait(1), "Snapshot worker must finish before the fixture closes its database"


def test_unexpected_visual_error_closes_without_private_values(
    client, configuration, monkeypatch, caplog
):
    """Contain unexpected stream failures without transmitting or logging payloads."""
    run = create_run(client, configuration)
    _issue_viewer(client, run["run_id"])

    def unavailable(*args):
        raise RuntimeError("PRIVATE_ERROR_SENTINEL")

    monkeypatch.setattr(client.app.state.reader, "snapshot", unavailable)
    with client.websocket_connect(
        f"ws://127.0.0.1:8000/v1/runs/{run['run_id']}/visual", headers={"Origin": ORIGIN}
    ) as socket:
        message = socket.receive()
        assert message["type"] == "websocket.close"
        assert message["code"] == 1011
        assert "PRIVATE_ERROR_SENTINEL" not in str(message)
    assert "PRIVATE_ERROR_SENTINEL" not in caplog.text


def test_operator_session_cannot_take_client_permissions(client, configuration):
    """Reject browser-supplied claims and credentials that cannot provision sessions."""
    run = create_run(client, configuration)
    route = f"/v1/operator/runs/{run['run_id']}/viewer-session"
    for claims in (
        {"role": "operator"},
        {"allowed_actions": ["delete"]},
        {"run_id": "another-run"},
    ):
        response = client.post(route, json=claims, headers=operator_headers("claims"))
        assert response.status_code == 422
    for credential in ("c", "e"):
        assert (
            client.post(
                route,
                json={},
                headers={
                    "Authorization": "Bearer " + credential * 32,
                    "Idempotency-Key": "forbidden-issue",
                },
            ).status_code
            == 403
        )
    _issue_viewer(client, run["run_id"])
    assert (
        client.post(route, json={}, headers={"Idempotency-Key": "viewer-issue"}).status_code == 403
    )


def test_viewer_scope_and_private_roles_are_enforced(client, configuration):
    """Keep private records, configuration writes, and other runs outside viewer scope."""
    first = create_run(client, configuration, "first")
    other = create_run(client, configuration, "other")
    session = _issue_viewer(client, first["run_id"])
    viewer_headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": session.json()["csrf_token"],
        "Idempotency-Key": "scoped",
    }
    consumer_headers = {"Authorization": "Bearer " + "c" * 32, "Idempotency-Key": "consumer"}
    for headers in (viewer_headers, consumer_headers):
        for route in (
            f"/v1/evaluation/runs/{first['run_id']}/truth",
            f"/v1/operator/runs/{first['run_id']}/manifest",
        ):
            assert client.get(route, headers=headers).status_code == 403
        for route in ("/v1/configurations", "/v1/configurations/validate"):
            assert client.post(route, json=configuration, headers=headers).status_code == 403
        assert (
            client.post(
                "/v1/runs", json={"configuration_id": "arbitrary"}, headers=headers
            ).status_code
            == 403
        )
        assert (
            client.post(
                f"/v1/runs/{other['run_id']}/control", json={"action": "start"}, headers=headers
            ).status_code
            == 403
        )
    for suffix in ("", "/snapshot", "/trajectory"):
        assert client.get(f"/v1/runs/{other['run_id']}{suffix}").status_code == 403
    for route in ("/v1/telemetry", "/v1/events"):
        assert (
            client.get(route, params={"stream_id": other["satellites"][0]["stream_id"]}).status_code
            == 403
        )
    assert {stream["run_id"] for stream in client.get("/v1/streams").json()["items"]} == {
        first["run_id"]
    }


def test_viewer_mutation_requires_origin_and_session_csrf(client, configuration):
    """Reject absent, foreign, and mismatched browser mutation credentials."""
    run = create_run(client, configuration)
    session = _issue_viewer(client, run["run_id"])
    for extra in (
        {},
        {"Origin": "https://foreign.test", "X-CSRF-Token": session.json()["csrf_token"]},
        {"Origin": ORIGIN, "X-CSRF-Token": "wrong"},
    ):
        response = client.post(
            f"/v1/runs/{run['run_id']}/control",
            json={"action": "start"},
            headers={"Idempotency-Key": "no-csrf", **extra},
        )
        assert response.status_code == 403
    assert client.app.state.repository.status(run["run_id"])["status"] == "created"


def test_deployed_bootstrap_requires_issued_session(settings, configuration):
    """A nonlocal deployment can resume an operator-issued session but cannot mint one."""
    app = create_app(replace(settings, local_demo=False), setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url="http://deployment.test") as client:
        run = create_run(client, configuration)
        app.state.service.demo_run_id = run["run_id"]
        assert client.get("/v1/viewer/bootstrap").status_code == 403
        _issue_viewer(client, run["run_id"])
        assert client.get("/v1/viewer/bootstrap").json()["run"]["run_id"] == run["run_id"]


def test_public_demo_is_read_only_and_rotates_after_terminal(settings):
    """Issue an HTTPS demo grant without exposing shared controls or old history."""
    public_settings = replace(
        settings,
        local_demo=False,
        public_demo=True,
        cookie_secure=True,
        origins=("https://demo.test",),
        demo_config=Path("configs/public-demo.yaml"),
    )
    app = create_app(public_settings, setup_schema=True)
    with TestClient(app, base_url="https://demo.test") as client:
        first = client.get("/v1/viewer/bootstrap")
        assert first.status_code == 200, first.text
        first_run_id = first.json()["run"]["run_id"]
        assert first.json()["run"]["status"] == "running"
        assert first.json()["allowed_actions"] == []
        assert "HttpOnly" in first.headers["set-cookie"]
        assert "SameSite=strict" in first.headers["set-cookie"]
        assert "; Secure" in first.headers["set-cookie"]
        for action in ("start", "pause", "resume", "set_speed", "stop"):
            body = {"action": action}
            if action == "set_speed":
                body["speed"] = 1
            response = client.post(
                f"/v1/runs/{first_run_id}/control",
                json=body,
                headers={
                    "Origin": "https://demo.test",
                    "X-CSRF-Token": first.json()["csrf_token"],
                    "Idempotency-Key": f"public-{action}",
                },
            )
            assert response.status_code == 403, response.text
        assert client.get(f"/v1/operator/runs/{first_run_id}/manifest").status_code == 403
        assert (
            client.get(
                "/v1/viewer/bootstrap", headers={"Origin": "https://foreign.test"}
            ).status_code
            == 403
        )
        stopped = client.post(
            f"/v1/runs/{first_run_id}/control",
            json={"action": "stop"},
            headers=operator_headers("operator-stop"),
        )
        assert stopped.status_code == 200, stopped.text
        second = client.get("/v1/viewer/bootstrap")
        assert second.status_code == 200, second.text
        assert second.json()["run"]["run_id"] != first_run_id
        assert second.json()["run"]["status"] == "running"
        assert app.state.repository.status(first_run_id)["status"] == "stopped"
        with app.state.database.engine.connect() as connection:
            assert (
                connection.scalar(
                    select(func.count())
                    .select_from(tables.frames)
                    .where(tables.frames.c.run_id == first_run_id)
                )
                == 0
            )
        public_cookie = client.cookies.get(COOKIE)
    disabled = create_app(replace(public_settings, public_demo=False), prepare_demo=False)
    with TestClient(disabled, base_url="https://demo.test") as client:
        client.cookies.set(COOKIE, public_cookie)
        assert client.get("/v1/viewer/bootstrap").status_code == 403


def test_public_demo_requires_secure_allowed_host(settings):
    """Keep anonymous remote issuance closed unless HTTPS settings match the host."""
    for secure, host, expected in (
        (False, "demo.test", 403),
        (True, "wrong.test", 403),
        (True, "demo.test", 200),
    ):
        public_settings = replace(
            settings,
            local_demo=False,
            public_demo=True,
            cookie_secure=secure,
            origins=("https://demo.test",),
            demo_config=Path("configs/public-demo.yaml"),
            database_url=settings.database_url.replace(
                "test.sqlite", f"public-{secure}-{host}.sqlite"
            ),
        )
        app = create_app(public_settings, setup_schema=True)
        with TestClient(app, base_url=f"https://{host}") as client:
            response = client.get("/v1/viewer/bootstrap")
            assert response.status_code == expected, response.text


def test_public_demo_limits_visual_connections(settings):
    """Reject excess public sockets and release the slot on disconnect."""
    public_settings = replace(
        settings,
        local_demo=False,
        public_demo=True,
        cookie_secure=True,
        origins=("https://demo.test",),
        demo_config=Path("configs/public-demo.yaml"),
        public_viewer_limit=1,
    )
    app = create_app(public_settings, setup_schema=True)
    with TestClient(app, base_url="https://demo.test") as client:
        run_id = client.get("/v1/viewer/bootstrap").json()["run"]["run_id"]
        path = f"wss://demo.test/v1/runs/{run_id}/visual"
        headers = {"Origin": "https://demo.test"}
        with client.websocket_connect(path, headers=headers) as first:
            assert first.receive_json()["run_id"] == run_id
            with pytest.raises(WebSocketDisconnect) as error:
                with client.websocket_connect(path, headers=headers):
                    pass
            assert error.value.code == 1013
        with client.websocket_connect(path, headers=headers) as replacement:
            assert replacement.receive_json()["run_id"] == run_id


@pytest.mark.parametrize("local", [True, False])
def test_only_local_bootstrap_switches_an_existing_session_to_new_demo(
    settings, configuration, local
):
    """A prepared replacement demo supersedes old cookies only through local issuance."""
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    with TestClient(app, base_url=ORIGIN if local else "http://deployment.test") as client:
        previous = create_run(client, configuration, "previous")
        _issue_viewer(client, previous["run_id"])
        old_cookie = client.cookies.get(COOKIE)
        current = create_run(client, configuration, "replacement")
        app.state.service.demo_run_id = current["run_id"]
        response = client.get("/v1/viewer/bootstrap")
        expected = current if local else previous
        assert (
            response.status_code == 200 and response.json()["run"]["run_id"] == expected["run_id"]
        )
        assert (client.cookies.get(COOKIE) != old_cookie) is local
        forbidden = previous if local else current
        assert client.get(f"/v1/runs/{forbidden['run_id']}").status_code == 403


def test_expired_and_tampered_sessions_cannot_reconnect(client, configuration):
    """Reject an expired or forged capability for HTTP and WebSocket access."""
    run = create_run(client, configuration)
    context = client.app.state
    cookie, _ = context.auth.issue(run["run_id"])
    claims = context.auth.serializer.loads(cookie)
    claims["expires_at"] = time.time() - 1
    for invalid in (cookie + "tampered", context.auth.serializer.dumps(claims)):
        client.cookies.clear()
        client.cookies.set(COOKIE, invalid)
        assert client.get(f"/v1/runs/{run['run_id']}").status_code == 401
        with pytest.raises(WebSocketDisconnect) as failure:
            with client.websocket_connect(
                f"ws://127.0.0.1:8000/v1/runs/{run['run_id']}/visual", headers={"Origin": ORIGIN}
            ):
                pytest.fail("Invalid viewer session connected")
        assert failure.value.code == 1008


def test_visual_socket_rejects_foreign_origin_and_other_run(client, configuration):
    """Apply origin and run scopes before accepting a presentation socket."""
    run = create_run(client, configuration)
    _issue_viewer(client, run["run_id"])
    with client.websocket_connect(
        f"ws://127.0.0.1:8000/v1/runs/{run['run_id']}/visual", headers={"Origin": ORIGIN}
    ) as socket:
        assert socket.receive_json()["type"] == "snapshot"
    for run_id, headers in (
        (run["run_id"], {}),
        (run["run_id"], {"Origin": "https://foreign.test"}),
        ("another-run", {"Origin": ORIGIN}),
    ):
        with pytest.raises(WebSocketDisconnect) as failure:
            with client.websocket_connect(
                f"ws://127.0.0.1:8000/v1/runs/{run_id}/visual", headers=headers
            ):
                pytest.fail("Unauthorized viewer socket connected")
        assert failure.value.code == 1008
