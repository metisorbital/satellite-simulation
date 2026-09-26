"""Named-session-only private operator case workflow endpoints."""

from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from metis_sim.adapters.records import canonical_hash
from metis_sim.adapters.repository import Idempotent
from metis_sim.api.auth import Principal
from metis_sim.api.requests import body_text, mutation_token, parse_json
from metis_sim.application.errors import ServiceError
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
    body = parse_json(await body_text(request))
    command = RecommendationCaseRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.cases.recommendation,
        case_id,
        principal.user_id,
        command.revision,
        command.recommendation,
        command.expected_effect,
        command.tradeoffs,
        _token(request, principal, body),
    )


@router.post("/v1/viewer/cases/{case_id}/decision", response_model=CaseRecord)
async def record_decision(case_id: str, request: Request) -> dict:
    """Record a human decision without issuing a simulator command."""
    principal = _operator(request, mutation=True)
    body = parse_json(await body_text(request))
    command = DecisionCaseRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.cases.decision,
        case_id,
        principal.user_id,
        command.revision,
        command.decision,
        command.reason,
        command.revised_recommendation,
        _token(request, principal, body),
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
