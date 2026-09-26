"""Role-scoped REST routes; private domain records have no generic serializer."""

import json
import time
from dataclasses import asdict
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query, Request, Response
from starlette.concurrency import run_in_threadpool

from metis_sim.adapters.configuration import normalize_configuration
from metis_sim.adapters.records import prior_result, record_result
from metis_sim.adapters.reports import telemetry_report
from metis_sim.api.auth import ACTIONS, COOKIE, Principal
from metis_sim.api.requests import (
    CreateRunRequest,
    ViewerConfigurationRequest,
    ViewerLoginRequest,
    body_text,
    configuration_body,
    mutation_token,
    parse_json,
)
from metis_sim.application.errors import ServiceError
from metis_sim.domain.catalog import CATALOGS
from metis_sim.domain.public import (
    ControlRequest,
    PublicRunStatus,
    Snapshot,
    Trajectory,
    ViewerBootstrap,
)
from metis_sim.domain.reports import TelemetryReport

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
def catalog(
    request: Request, version: Literal["power-leo.v1", "spacecraft.v1"] = "power-leo.v1"
) -> dict:
    """Expose only public channel and physical-model descriptors."""
    request.app.state.auth.principal(request).require(PUBLIC_READERS)
    return {
        "catalog_version": version,
        "schema_version": "telemetry.v1",
        "models": {
            "orbit": "j2_cartesian",
            "earth": "wgs84_j2_v1",
            "sun": "astropy_builtin",
            **(
                {
                    "electrical": "ideal_regulated_rails_v1",
                    "thermal": "three_node_euler_fixed_1s_v1",
                    "payload": "power_gated_camera_storage_v1",
                    "attitude": "ideal_lvlh_v1",
                    "magnetic": "centered_axial_dipole_v1",
                }
                if version == "spacecraft.v1"
                else {}
            ),
        },
        "channels": [asdict(channel) for channel in CATALOGS[version]],
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
    if command.action == "start" and principal.interactive:
        await run_in_threadpool(context.service.ensure_prepared_viewer_run, run_id)
    return await run_in_threadpool(
        context.runner.command,
        run_id,
        command.action,
        command.speed,
        mutation_token(request, principal, body),
        user_id=principal.user_id,
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


@router.get("/v1/runs/{run_id}/telemetry-report", response_model=TelemetryReport)
def report(
    run_id: str,
    request: Request,
    from_sequence: int = Query(0, ge=0, le=86400),
    through_sequence: int | None = Query(None, ge=0, le=86400),
) -> TelemetryReport:
    """Report retained public telemetry at a fixed committed boundary.

    Parameters
    ----------
    run_id : str
        Run whose committed measurements should be summarized.
    request : Request
        Authenticated HTTP request; viewer sessions remain run-scoped.
    from_sequence, through_sequence : int and int or None
        Inclusive window, with the current committed tick as the default end.

    Returns
    -------
    TelemetryReport
        Public statistics, coverage and model limits, excluding evaluator labels.
    """
    context = request.app.state
    context.auth.principal(request).require(PUBLIC_READERS, run_id)
    return telemetry_report(context.database, run_id, from_sequence, through_sequence)


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


def _session_bootstrap(request: Request, principal: Principal) -> ViewerBootstrap:
    """Project the session's run and its optional private operator identity."""
    context = request.app.state
    operator = None
    if principal.user_id is not None:
        try:
            run = context.repository.private_run(principal.run_id)
        except ServiceError as error:
            if error.code == "run_not_found":
                raise ServiceError(
                    "session_expired", "Sign in to start a new demo session.", 401
                ) from error
            raise
        if run["user_id"] != principal.user_id:
            raise ServiceError("unauthorized", "Viewer session does not match the run owner.", 401)
        operator = context.auth.operators_by_id[principal.user_id]
    if principal.interactive:
        context.service.ensure_prepared_viewer_run(principal.run_id)
    return ViewerBootstrap.model_validate(
        {
            "csrf_token": principal.csrf_token,
            "allowed_actions": list(principal.allowed_actions),
            "run": context.repository.status(principal.run_id),
            "operator": operator,
        }
    )


@router.get("/v1/viewer/session", response_model=ViewerBootstrap)
def viewer_session(request: Request) -> ViewerBootstrap:
    """Resume a mock operator session without issuing an anonymous grant.

    Parameters
    ----------
    request : Request
        Browser request carrying an existing mock operator cookie.

    Returns
    -------
    ViewerBootstrap
        The same scoped run and identity used before page reload.

    Raises
    ------
    ServiceError
        With status 401 when a mock operator has not signed in.
    """
    context = request.app.state
    principal = context.auth.session(request)
    context.auth.origin(request)
    if principal.user_id is None:
        raise ServiceError("unauthorized", "Sign in with a demo operator.", 401)
    return _session_bootstrap(request, principal)


@router.post("/v1/viewer/login", response_model=ViewerBootstrap)
async def viewer_login(request: Request, response: Response) -> ViewerBootstrap:
    """Select a mock identity and prepare its independent interactive run.

    Parameters
    ----------
    request : Request
        Allowed demo-origin request containing a login and nonempty password.
    response : Response
        Response receiving the signed HttpOnly session cookie.

    Returns
    -------
    ViewerBootstrap
        Run-scoped controls and the selected mock operator identity.

    Notes
    -----
    Passwords are not verified, logged, hashed, or persisted. Repeating login
    for the current operator preserves its run; switching requires logout.
    """
    context = request.app.state
    context.auth.login_issuance(request)
    command = ViewerLoginRequest.model_validate(parse_json(await body_text(request)))
    operator = context.auth.demo_operator(command.login)
    user_id = str(operator.user_id)
    try:
        current = context.auth.session(request)
    except ServiceError as error:
        if error.status != 401:
            raise
    else:
        if current.user_id is not None:
            try:
                resumed = await run_in_threadpool(_session_bootstrap, request, current)
            except ServiceError as error:
                if error.status != 401:
                    raise
            else:
                if current.user_id == user_id:
                    return resumed
                raise ServiceError("logout_required", "Log out before switching operators.", 409)
    expires_at = time.time() + context.settings.session_lifetime_s
    run = await run_in_threadpool(
        context.service.create_viewer_template_run,
        context.settings.demo_config,
        context.settings.session_lifetime_s,
        user_id=user_id,
        viewer_expires_at=expires_at,
    )
    return _viewer_bootstrap_response(request, response, run, user_id=user_id)


@router.post("/v1/viewer/logout")
async def viewer_logout(request: Request, response: Response) -> dict:
    """End a browser session after stopping only its operator's active run.

    Parameters
    ----------
    request : Request
        Empty-object request with Origin and, for valid sessions, CSRF token.
    response : Response
        Response that clears the HttpOnly session cookie.

    Returns
    -------
    dict
        Empty acknowledgement after successful cleanup and cookie removal.

    Notes
    -----
    Missing or expired cookies can be cleared without a CSRF token. Created
    and terminal runs retain their history and private operator association.
    """
    context = request.app.state
    context.auth.origin(request, required=True)
    body = parse_json(await body_text(request))
    if body:
        raise ServiceError("invalid_logout", "Logout request must be an empty object.", 422)
    try:
        principal = context.auth.session(request)
    except ServiceError as error:
        if error.status != 401:
            raise
    else:
        context.auth.csrf(request, principal)
        if principal.user_id is not None:
            await run_in_threadpool(
                context.service.stop_viewer_run,
                principal.run_id,
                principal.user_id,
                actor_user_id=principal.user_id,
            )
    response.delete_cookie(
        COOKIE,
        path="/",
        httponly=True,
        secure=context.settings.cookie_secure or request.url.scheme == "https",
        samesite="strict",
    )
    return {}


@router.get("/v1/viewer/bootstrap", response_model=ViewerBootstrap)
def bootstrap(request: Request, response: Response) -> ViewerBootstrap:
    """Resume a scoped session or issue an explicitly enabled demo grant."""
    context = request.app.state
    try:
        principal = context.auth.principal(request)
        principal.require({"viewer_control"})
        context.auth.origin(request)
    except ServiceError:
        principal = None
    if principal is not None and principal.user_id is not None:
        return _session_bootstrap(request, principal)
    public_demo = False
    interactive = False
    try:
        context.auth.local_bootstrap(request)
    except ServiceError:
        try:
            context.auth.public_bootstrap(request)
        except ServiceError:
            if principal is None:
                raise
            run_id = principal.run_id
        else:
            if principal is not None and not principal.public_demo:
                run_id = principal.run_id
                if principal.interactive:
                    context.service.ensure_prepared_viewer_run(run_id)
            elif context.settings.interactive_public_demo:
                run_id = context.service.create_viewer_template_run(
                    context.settings.demo_config, context.settings.session_lifetime_s
                )["run_id"]
                interactive = True
            else:
                run_id = context.service.ensure_public_demo(context.settings.demo_config)
                public_demo = True
    else:
        run_id = (
            principal.run_id
            if principal is not None and principal.interactive
            else context.service.demo_run_id
            or (principal.run_id if principal is not None else None)
        )
    if run_id is None:
        raise ServiceError(
            "demo_not_prepared", "Start the server with an explicitly prepared demo.", 503
        )
    if principal is None or principal.run_id != run_id:
        cookie, principal = context.auth.issue(
            run_id, public_demo=public_demo, interactive=interactive
        )
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
        allowed_actions=list(principal.allowed_actions),
        run=PublicRunStatus.model_validate(context.repository.status(run_id)),
    )


@router.get("/v1/viewer/configuration")
def viewer_configuration(request: Request) -> dict:
    """Return editable spacecraft inputs without private configuration fields."""
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require({"viewer_control"}, action="start")
    return {"satellites": context.service.editable_satellites(principal.run_id)}


def _viewer_bootstrap_response(
    request: Request,
    response: Response,
    run: dict,
    *,
    user_id: str | None = None,
) -> ViewerBootstrap:
    """Issue a cookie using the run's durable mock lease, including on retries."""
    context = request.app.state
    expires_at = (
        context.repository.private_run(run["run_id"])["manifest"]["viewer_expires_at"]
        if user_id is not None
        else None
    )
    cookie, principal = context.auth.issue(
        run["run_id"], interactive=True, user_id=user_id, expires_at=expires_at
    )
    response.set_cookie(
        COOKIE,
        cookie,
        max_age=max(0, int(principal.expires_at - time.time())),
        httponly=True,
        secure=context.settings.cookie_secure or request.url.scheme == "https",
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return ViewerBootstrap(
        csrf_token=principal.csrf_token,
        allowed_actions=list(principal.allowed_actions),
        run=PublicRunStatus.model_validate(run),
        operator=context.auth.operators_by_id.get(user_id),
    )


@router.post("/v1/viewer/configuration", response_model=ViewerBootstrap)
async def replace_viewer_configuration(request: Request, response: Response) -> ViewerBootstrap:
    """Create a new run with edited spacecraft under the current viewer grant."""
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require({"viewer_control"}, action="start")
    context.auth.csrf(request, principal)
    body = parse_json(await body_text(request))
    command = ViewerConfigurationRequest.model_validate(body)
    expires_at = time.time() + context.settings.session_lifetime_s if principal.user_id else None
    run = await run_in_threadpool(
        context.service.recreate_viewer_run,
        principal.run_id,
        command.satellites,
        mutation_token(request, principal, body),
        viewer_expires_at=expires_at,
    )
    return _viewer_bootstrap_response(request, response, run, user_id=principal.user_id)


@router.post("/v1/viewer/reset", response_model=ViewerBootstrap)
async def reset_viewer_run(request: Request, response: Response) -> ViewerBootstrap:
    """Restart from tick zero by allocating fresh run and stream identities."""
    context = request.app.state
    principal = context.auth.principal(request)
    principal.require({"viewer_control"}, action="start")
    context.auth.csrf(request, principal)
    body = parse_json(await body_text(request))
    if body:
        raise ServiceError("invalid_reset", "Reset request must be an empty object.", 422)
    expires_at = time.time() + context.settings.session_lifetime_s if principal.user_id else None
    run = await run_in_threadpool(
        context.service.recreate_viewer_run,
        principal.run_id,
        None,
        mutation_token(request, principal, body),
        viewer_expires_at=expires_at,
    )
    return _viewer_bootstrap_response(request, response, run, user_id=principal.user_id)


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
                "bootstrap": {
                    "csrf_token": viewer.csrf_token,
                    "allowed_actions": list(viewer.allowed_actions),
                    "run": status,
                },
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
    return ViewerBootstrap.model_validate({**result["bootstrap"], "allowed_actions": list(ACTIONS)})
