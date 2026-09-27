"""Named-session-only private operator case workflow endpoints."""

from collections.abc import Callable
from contextlib import nullcontext
from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from metis_sim.adapters.records import canonical_hash
from metis_sim.adapters.repository import Idempotent
from metis_sim.api.auth import Principal
from metis_sim.api.requests import body_text, mutation_token, parse_json
from metis_sim.application.errors import ServiceError
from metis_sim.application.mission_cases import proposal_recommendation
from metis_sim.domain.cases import (
    AssessmentCaseRequest,
    CaptureCaseEvidenceRequest,
    CaseList,
    CaseRecord,
    CreateCaseRequest,
    DecisionCaseRequest,
    OutcomeCaseRequest,
    RecommendationCaseRequest,
)

router = APIRouter(tags=["Private operator cases"])


def _operator(request: Request, *, mutation: bool = False) -> Principal:
    """Require a named interactive operator session for private case access.

    Parameters
    ----------
    request : Request
        Browser request carrying the signed run-scoped operator session.
    mutation : bool, default=False
        Require the session-bound CSRF token for a state-changing request.

    Returns
    -------
    Principal
        Named authenticated operator. Historical case reads and edits are
        later restricted by the durable stored case owner, not the current
        run scope alone.
    """
    context = request.app.state
    principal = context.auth.session(request)
    principal.require({"viewer_control"})
    context.auth.origin(request)
    if principal.user_id is None or principal.public_demo or not principal.interactive:
        raise ServiceError("forbidden", "Sign in with a named operator to access cases.", 403)
    if mutation:
        context.auth.csrf(request, principal)
    return principal


def _current_run_operator(request: Request, run_id: str, *, mutation: bool) -> Principal:
    """Require that case creation targets the session's current owned run."""
    principal = _operator(request, mutation=mutation)
    principal.require({"viewer_control"}, run_id)
    run = request.app.state.repository.private_run(run_id)
    if run["user_id"] != principal.user_id:
        raise ServiceError("forbidden", "This run belongs to another operator.", 403)
    return principal


def _token(request: Request, principal: Principal, body: dict[str, Any]) -> Idempotent:
    """Bind a mutation retry to its named operator as well as route and body."""
    scope, key, digest = mutation_token(request, principal, body)
    identity = canonical_hash({"scope": scope, "user_id": principal.user_id})
    return f"cases:{identity}", key, digest


def _mission_decision(request: Request, record: dict[str, Any], decision: str) -> str | None:
    """Resolve a linked saved proposal without changing historical replay plans.

    Parameters
    ----------
    request : Request
        Authenticated workflow request.
    record : dict
        Owned durable case record.
    decision : str
        Case decision, or ``pending`` after a recommendation edit.

    Returns
    -------
    str or None
        Mission action while held at its decision, or ``None`` for ordinary
        cases and historical audit updates after playback has continued.
    """
    metis = getattr(request.app.state, "metis", None)
    if metis is None:
        return None
    state = metis.store.get(record["run_id"], record["user_id"])
    if state is None or state.get("case_id") != record["case_id"]:
        return None
    status = request.app.state.repository.status(record["run_id"])
    if (
        status["status"] in {"completed", "stopped", "failed", "aborted"}
        or int(status["committed_tick"]) > state["alert_at_s"]
    ):
        return None
    if decision in {"pending", "revised"}:
        return "pending"
    if decision == "approved" and record["recommendation"] != proposal_recommendation(
        state["proposal"]
    ):
        return "reviewed"
    return decision


def _validate_mission_decision(request: Request, case_id: str, user_id: str, decision: str) -> None:
    """Validate a linked mission action before accepting the case mutation.

    Parameters
    ----------
    request : Request
        Authenticated workflow request.
    case_id, user_id : str
        Owned case and authenticated operator identity.
    decision : str
        Requested case decision or recommendation reset.
    """
    record = request.app.state.cases.detail(case_id, user_id)
    action = _mission_decision(request, record, decision)
    if action is not None:
        request.app.state.metis.validate_case_resolution(record["run_id"], user_id, case_id, action)


def _sync_mission_decision(request: Request, case_id: str, user_id: str) -> None:
    """Project the latest audited case decision and resume the same replay.

    Parameters
    ----------
    request : Request
        Authenticated workflow request.
    case_id, user_id : str
        Case and its authenticated owner. Reading current state makes a retry
        of an earlier response unable to overwrite a later case decision.
    """
    record = request.app.state.cases.detail(case_id, user_id)
    action = _mission_decision(request, record, record["decision"])
    if action is not None:
        operator = request.app.state.auth.operators_by_id[user_id].display_name
        request.app.state.metis.resolve_case(record["run_id"], user_id, case_id, action, operator)


def _review_change(
    request: Request,
    case_id: str,
    user_id: str,
    decision: str,
    change: Callable[[], dict[str, Any]],
    mission_proposal_id: str | None = None,
) -> dict[str, Any]:
    """Serialize audited review with the linked mission projection.

    Parameters
    ----------
    request : Request
        Authenticated case request.
    case_id, user_id : str
        Owned case and authenticated reviewer.
    decision : str
        Proposed decision or pending recommendation reset.
    change : callable
        Revision-checked, idempotent database case mutation.
    mission_proposal_id : str or None
        Additional saved-proposal precondition for a direct banner approval.

    Returns
    -------
    dict
        Durable case result. A failed mission projection can be retried with
        the same key without duplicating case history.
    """
    metis = getattr(request.app.state, "metis", None)
    with metis.case_workflow() if metis is not None else nullcontext():
        if mission_proposal_id is not None:
            record = request.app.state.cases.detail(case_id, user_id)
            state = metis.store.get(record["run_id"], user_id) if metis is not None else None
            principal = request.app.state.auth.session(request)
            if (
                state is None
                or record["run_id"] != principal.run_id
                or state.get("case_id") != case_id
                or state.get("status") not in {"awaiting_decision", "approved"}
                or state["proposal"]["proposal_id"] != mission_proposal_id
                or record["recommendation"] != proposal_recommendation(state["proposal"])
            ):
                raise ServiceError(
                    "proposal_changed",
                    "The saved plan changed. Review the investigation before approving.",
                    409,
                )
        _validate_mission_decision(request, case_id, user_id, decision)
        result = change()
        _sync_mission_decision(request, case_id, user_id)
        return result


@router.get("/v1/viewer/cases", response_model=CaseList)
async def list_cases(request: Request) -> dict:
    """Read at most 100 private historical cases owned by the signed-in operator."""
    principal = _operator(request)
    return await run_in_threadpool(request.app.state.cases.list_cases, principal.user_id)


@router.get("/v1/viewer/cases/{case_id}", response_model=CaseRecord)
async def case_detail(case_id: str, request: Request) -> dict:
    """Read the signed-in operator's full private case and bounded timeline."""
    principal = _operator(request)
    return await run_in_threadpool(request.app.state.cases.detail, case_id, principal.user_id)


@router.post("/v1/runs/{run_id}/cases", response_model=CaseRecord)
async def create_case(run_id: str, request: Request) -> dict:
    """Create a case for the current owned run and capture selected public evidence."""
    principal = _current_run_operator(request, run_id, mutation=True)
    body = parse_json(await body_text(request))
    command = CreateCaseRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.cases.create,
        run_id,
        principal.user_id,
        command.satellite_id,
        command.title,
        command.summary,
        command.priority,
        command.sequence,
        _token(request, principal, body),
    )


@router.post("/v1/viewer/cases/{case_id}/assessment", response_model=CaseRecord)
async def update_assessment(case_id: str, request: Request) -> dict:
    """Store operator assessment and missing-information text at one revision."""
    principal = _operator(request, mutation=True)
    body = parse_json(await body_text(request))
    command = AssessmentCaseRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.cases.assessment,
        case_id,
        principal.user_id,
        command.revision,
        command.assessment,
        command.missing_information,
        _token(request, principal, body),
    )


@router.post("/v1/viewer/cases/{case_id}/recommendation", response_model=CaseRecord)
async def update_recommendation(case_id: str, request: Request) -> dict:
    """Store the operator-authored recommendation and stated tradeoffs."""
    principal = _operator(request, mutation=True)
    assert principal.user_id is not None
    body = parse_json(await body_text(request))
    command = RecommendationCaseRequest.model_validate(body)
    return await run_in_threadpool(
        _review_change,
        request,
        case_id,
        principal.user_id,
        "pending",
        lambda: request.app.state.cases.recommendation(
            case_id,
            principal.user_id,
            command.revision,
            command.recommendation,
            command.expected_effect,
            command.tradeoffs,
            _token(request, principal, body),
        ),
    )


@router.post("/v1/viewer/cases/{case_id}/decision", response_model=CaseRecord)
async def record_decision(case_id: str, request: Request) -> dict:
    """Record human review and continue a linked recorded mission when resolved."""
    principal = _operator(request, mutation=True)
    assert principal.user_id is not None
    body = parse_json(await body_text(request))
    command = DecisionCaseRequest.model_validate(body)
    return await run_in_threadpool(
        _review_change,
        request,
        case_id,
        principal.user_id,
        command.decision,
        lambda: request.app.state.cases.decision(
            case_id,
            principal.user_id,
            command.revision,
            command.decision,
            command.reason,
            command.revised_recommendation,
            _token(request, principal, body),
        ),
        command.mission_proposal_id,
    )


@router.post("/v1/viewer/cases/{case_id}/outcome", response_model=CaseRecord)
async def record_outcome(case_id: str, request: Request) -> dict:
    """Record observed outcome evidence independently of approval state."""
    principal = _operator(request, mutation=True)
    body = parse_json(await body_text(request))
    command = OutcomeCaseRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.cases.outcome,
        case_id,
        principal.user_id,
        command.revision,
        command.outcome,
        command.outcome_notes,
        command.close_case,
        _token(request, principal, body),
    )


@router.post("/v1/viewer/cases/{case_id}/evidence", response_model=CaseRecord)
async def capture_evidence(case_id: str, request: Request) -> dict:
    """Append the latest committed public sample from the case's original run."""
    principal = _operator(request, mutation=True)
    body = parse_json(await body_text(request))
    command = CaptureCaseEvidenceRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.cases.capture_evidence,
        case_id,
        principal.user_id,
        command.revision,
        principal.run_id,
        _token(request, principal, body),
    )
