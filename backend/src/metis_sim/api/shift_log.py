"""Named-session-only operator Shift Log endpoints."""

from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from metis_sim.adapters.records import canonical_hash
from metis_sim.adapters.repository import Idempotent
from metis_sim.api.auth import Principal
from metis_sim.api.requests import body_text, mutation_token, parse_json
from metis_sim.application.errors import ServiceError
from metis_sim.domain.shift_log import (
    AddShiftLogEntryRequest,
    ShiftLog,
    ShiftLogList,
    SubmitShiftLogRequest,
    UpdateShiftLogSummaryRequest,
)

router = APIRouter(tags=["Private operator Shift Log"])


def _operator(request: Request, run_id: str, *, mutation: bool = False) -> Principal:
    """Require a named browser identity that owns the requested run.

    Parameters
    ----------
    request : Request
        Browser request whose signed cookie identifies the actor.
    run_id : str
        Requested run, which must match both session scope and stored owner.
    mutation : bool, default=False
        Also require a trusted origin and matching CSRF token.

    Returns
    -------
    Principal
        Verified, named operator permitted to access this private record.
    """
    context = request.app.state
    principal = context.auth.session(request)
    principal.require({"viewer_control"}, run_id)
    context.auth.origin(request)
    if principal.user_id is None or principal.public_demo or not principal.interactive:
        raise ServiceError("forbidden", "Sign in with a named operator to access Shift Log.", 403)
    run = context.repository.private_run(run_id)
    if run["user_id"] != principal.user_id:
        raise ServiceError("forbidden", "Shift Log belongs to another operator.", 403)
    if mutation:
        context.auth.csrf(request, principal)
    return principal


def _token(request: Request, principal: Principal, body: dict[str, Any]) -> Idempotent:
    """Bind a retry to the authenticated author as well as route and run.

    Parameters
    ----------
    request : Request
        Mutation request with its required idempotency header.
    principal : Principal
        Named operator verified by the route authorization guard.
    body : dict
        Strictly parsed request used to detect conflicting retries.

    Returns
    -------
    Idempotent
        Bounded hashed scope, client key, and canonical request digest.
    """
    scope, key, digest = mutation_token(request, principal, body)
    identity = canonical_hash({"scope": scope, "user_id": principal.user_id})
    return f"shift-log:{identity}", key, digest


@router.get("/v1/runs/{run_id}/shift-logs", response_model=ShiftLogList)
def list_shift_logs(run_id: str, request: Request) -> dict:
    """Read the signed-in operator's retained shifts for this run.

    Parameters
    ----------
    run_id : str
        Run scoped by the authenticated cookie.
    request : Request
        Browser request carrying a named operator session.

    Returns
    -------
    dict
        Private, allowlisted shifts and entries for the owning operator.
    """
    principal = _operator(request, run_id)
    return request.app.state.shift_logs.list_logs(run_id, principal.user_id)


@router.post("/v1/runs/{run_id}/shift-logs/entries", response_model=ShiftLog)
async def add_shift_log_entry(run_id: str, request: Request) -> dict:
    """Append a narrative to the current draft, creating one when needed.

    Parameters
    ----------
    run_id : str
        Run scoped by the authenticated cookie.
    request : Request
        CSRF-protected request with a bounded entry and idempotency key.

    Returns
    -------
    dict
        Updated draft; author identity comes only from the verified session.
    """
    principal = _operator(request, run_id, mutation=True)
    body = parse_json(await body_text(request))
    command = AddShiftLogEntryRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.shift_logs.add_entry,
        run_id,
        principal.user_id,
        command.kind,
        command.text,
        _token(request, principal, body),
    )


@router.post("/v1/runs/{run_id}/shift-logs/{shift_id}/summary", response_model=ShiftLog)
async def update_shift_log_summary(run_id: str, shift_id: str, request: Request) -> dict:
    """Replace the owning operator's draft handover summary.

    Parameters
    ----------
    run_id, shift_id : str
        Authorized run and draft identities.
    request : Request
        CSRF-protected summary command with an idempotency key.

    Returns
    -------
    dict
        Updated draft record with its unchanged chronological entries.
    """
    principal = _operator(request, run_id, mutation=True)
    body = parse_json(await body_text(request))
    command = UpdateShiftLogSummaryRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.shift_logs.update_summary,
        run_id,
        principal.user_id,
        shift_id,
        command.summary,
        _token(request, principal, body),
    )


@router.post("/v1/runs/{run_id}/shift-logs/{shift_id}/submit", response_model=ShiftLog)
async def submit_shift_log(run_id: str, shift_id: str, request: Request) -> dict:
    """Freeze a draft as the owning operator's submitted handover record.

    Parameters
    ----------
    run_id, shift_id : str
        Authorized run and draft identities.
    request : Request
        CSRF-protected empty command with an idempotency key.

    Returns
    -------
    dict
        Frozen submitted record; subsequent entries create another draft.
    """
    principal = _operator(request, run_id, mutation=True)
    body = parse_json(await body_text(request))
    SubmitShiftLogRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.shift_logs.submit,
        run_id,
        principal.user_id,
        shift_id,
        _token(request, principal, body),
    )
