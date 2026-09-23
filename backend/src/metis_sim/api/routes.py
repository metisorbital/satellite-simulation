"""Role-scoped REST routes; private domain records have no generic serializer."""

import json
import time
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from metis_sim.adapters.configuration import normalize_configuration
from metis_sim.adapters.records import prior_result, record_result
from metis_sim.api.auth import COOKIE
from metis_sim.api.requests import (
    CreateRunRequest,
    body_text,
    configuration_body,
    mutation_token,
    parse_json,
)
from metis_sim.application.errors import ServiceError
from metis_sim.domain.catalog import CHANNELS
from metis_sim.domain.public import (
    ControlRequest,
    PublicRunStatus,
    Snapshot,
    Trajectory,
    ViewerBootstrap,
)

router = APIRouter()
PUBLIC_READERS = {"operator", "consumer", "viewer_control"}
VIEWERS = {"operator", "viewer_control"}


@router.get("/health/live")
def live() -> dict:
    """Return process liveness without performing model or database work."""
    return {"status": "alive"}


@router.get("/health/ready")
def ready(request: Request) -> dict:
    """Report initialized writer, database, and any persistence stop condition."""
    context = request.app.state
    if context.runner.failure or context.runner.backpressure or not context.database.healthy():
        raise ServiceError("not_ready", "Persistence is unavailable or under backpressure.", 503)
    return {"status": "ready", "writer": "single", "source_id": context.settings.source_id}


@router.get("/v1/catalog")
def catalog(request: Request) -> dict:
    """Expose only public channel and physical-model descriptors."""
    request.app.state.auth.principal(request).require(PUBLIC_READERS)
    return {
        "catalog_version": "power-leo.v1",
        "schema_version": "telemetry.v1",
        "models": {"orbit": "j2_cartesian", "earth": "wgs84_j2_v1", "sun": "astropy_builtin"},
        "channels": [asdict(channel) for channel in CHANNELS],
    }


@router.post("/v1/configurations/validate")
async def validate_configuration(request: Request) -> dict:
    """Validate YAML or JSON through the same schema, without creating a revision."""
    request.app.state.auth.principal(request).require({"operator"})
    config = await configuration_body(request)
    return {"valid": True, "normalized": normalize_configuration(config), "errors": []}


@router.post("/v1/configurations", status_code=201)
async def create_configuration(request: Request) -> dict:
    """Persist a new immutable configuration revision for an operator."""
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require({"operator"})
    config = await configuration_body(request)
    token = mutation_token(request, principal, config.model_dump(mode="json"))
    return await run_in_threadpool(context.service.create_configuration, config, token)


@router.post("/v1/runs", response_model=PublicRunStatus, status_code=201)
async def create_run(request: Request) -> dict:
    """Prepare an independent run without blocking the HTTP event loop."""
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require({"operator"})
    body = parse_json(await body_text(request))
    command = CreateRunRequest.model_validate(body)
    return await run_in_threadpool(
        context.service.create_run,
        command.configuration_id,
        command.retain,
        mutation_token(request, principal, body),
    )


@router.get("/v1/runs/{run_id}", response_model=PublicRunStatus)
def run_status(run_id: str, request: Request) -> dict:
    """Return the latest durably committed public run status."""
    context = request.app.state
    context.auth.principal(request).require(VIEWERS, run_id)
    return context.repository.status(run_id)


@router.post("/v1/runs/{run_id}/control", response_model=PublicRunStatus)
async def control(run_id: str, request: Request) -> dict:
    """Serialize scoped commands and acknowledge a durable tick boundary."""
    context = request.app.state
    principal = context.auth.principal(request)
    body = parse_json(await body_text(request))
    command = ControlRequest.model_validate(body)
    if (command.action == "set_speed") != (command.speed is not None):
        raise ServiceError("invalid_control", "Only set_speed requires a speed value.", 422)
    principal.require(VIEWERS, run_id, command.action)
    context.auth.csrf(request, principal)
    return await run_in_threadpool(
        context.runner.command,
        run_id,
        command.action,
        command.speed,
        mutation_token(request, principal, body),
    )


@router.get("/v1/streams")
def streams(request: Request) -> dict:
    """Discover public stream identities and retained ranges."""
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require(PUBLIC_READERS)
    return {
        "items": context.reader.streams(
            principal.run_id if principal.role == "viewer_control" else None
        )
    }


@router.get("/v1/telemetry")
def telemetry(
    request: Request,
    stream_id: str,
    after: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    """Replay immutable frames with stream-scoped durable cursors."""
    return _page(request, stream_id, after, limit, "telemetry")


@router.get("/v1/events")
def events(
    request: Request,
    stream_id: str,
    after: str | None = None,
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    """Replay observed public events in their independent sequence namespace."""
    return _page(request, stream_id, after, limit, "events")


def _page(request: Request, stream_id: str, after: str | None, limit: int, kind: str) -> dict:
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require(PUBLIC_READERS)
    principal.require(PUBLIC_READERS, context.reader.stream_run(stream_id))
    return context.reader.page(stream_id, after, limit, kind)


@router.get("/v1/runs/{run_id}/snapshot", response_model=Snapshot)
def snapshot(
    run_id: str, request: Request, at: datetime | None = None, history: int = Query(1, ge=1, le=41)
) -> Snapshot:
    """Read health and positions at one consistent committed boundary."""
    context = request.app.state
    context.auth.principal(request).require(VIEWERS, run_id)
    return Snapshot.model_validate_json(json.dumps(context.reader.snapshot(run_id, at, history)))


@router.get("/v1/runs/{run_id}/trajectory", response_model=Trajectory)
def trajectory(
    run_id: str,
    request: Request,
    start: int = Query(0, alias="from", ge=0),
    end: int = Query(3600, alias="to", ge=0),
    step_s: int = Query(30, ge=1),
) -> Trajectory:
    """Return bounded orbit-only samples from the backend trajectory."""
    context = request.app.state
    context.auth.principal(request).require(VIEWERS, run_id)
    return context.service.trajectory(run_id, start, end, step_s)


@router.get("/v1/evaluation/runs/{run_id}/truth")
def truth(
    run_id: str,
    request: Request,
    after: int = Query(-1, ge=-1),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    """Read private physical evaluation only with evaluator credentials."""
    context = request.app.state
    context.auth.principal(request).require({"evaluator"})
    context.repository.status(run_id)
    return context.reader.private_truth(run_id, after, limit)


@router.get("/v1/operator/runs/{run_id}/manifest")
def manifest(run_id: str, request: Request) -> dict:
    """Return the reproducibility manifest only to operator/evaluator principals."""
    context = request.app.state
    context.auth.principal(request).require({"operator", "evaluator"})
    return context.repository.private_run(run_id)["manifest"]


@router.get("/v1/viewer/bootstrap", response_model=ViewerBootstrap)
def bootstrap(request: Request, response: Response) -> ViewerBootstrap:
    """Resume a scoped session, preferring the prepared demo only on local loopback."""
    context = request.app.state
    try:
        principal = context.auth.principal(request)
        principal.require({"viewer_control"})
        context.auth.origin(request)
    except ServiceError:
        principal = None
    try:
        context.auth.local_bootstrap(request)
    except ServiceError:
        if principal is None:
            raise
        run_id = principal.run_id
    else:
        run_id = context.service.demo_run_id or (
            principal.run_id if principal is not None else None
        )
    if run_id is None:
        raise ServiceError(
            "demo_not_prepared", "Start the server with an explicitly prepared demo.", 503
        )
    if principal is None or principal.run_id != run_id:
        cookie, principal = context.auth.issue(run_id)
        response.set_cookie(
            COOKIE,
            cookie,
            max_age=context.settings.session_lifetime_s,
            httponly=True,
            secure=context.settings.cookie_secure or request.url.scheme == "https",
            samesite="strict",
            path="/",
        )
    response.headers["Cache-Control"] = "no-store"
    return ViewerBootstrap(
        csrf_token=principal.csrf_token,
        run=PublicRunStatus.model_validate(context.repository.status(run_id)),
    )


@router.post("/v1/operator/runs/{run_id}/viewer-session", response_model=ViewerBootstrap)
async def issue_viewer_session(
    run_id: str, request: Request, response: Response
) -> ViewerBootstrap:
    """Let an authenticated operator provision only a run-scoped browser capability."""
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require({"operator"})
    context.auth.origin(request)
    body = parse_json(await body_text(request))
    if body:
        raise ServiceError(
            "invalid_session_request",
            "Session permissions are fixed by the server; submit an empty object.",
            422,
        )
    token = mutation_token(request, principal, body)

    def provision() -> dict:
        with context.service.mutations, context.database.writer_transaction() as connection:
            existing = prior_result(connection, *token)
            if existing is not None:
                return existing
            status = context.repository.status(run_id)
            cookie, viewer = context.auth.issue(run_id)
            result = {
                "cookie": cookie,
                "expires_at": viewer.expires_at,
                "bootstrap": {"csrf_token": viewer.csrf_token, "run": status},
            }
            record_result(connection, *token, result)
            return result

    result = await run_in_threadpool(provision)
    response.set_cookie(
        COOKIE,
        result["cookie"],
        max_age=max(0, int(result["expires_at"] - time.time())),
        httponly=True,
        secure=context.settings.cookie_secure or request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    return ViewerBootstrap.model_validate(result["bootstrap"])
