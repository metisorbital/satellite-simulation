"""Named-session notification endpoints."""

from typing import Any

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from metis_sim.api.auth import Principal
from metis_sim.api.cases import _operator as _named_operator
from metis_sim.api.requests import body_text, mutation_token, parse_json
from metis_sim.application.errors import ServiceError
from metis_sim.domain.notifications import MarkNotificationReadRequest, NotificationList

router = APIRouter(tags=["Private operator notifications"])


def _current_run_operator(request: Request, *, mutation: bool = False) -> Principal:
    """Require a named operator whose session still owns its current run.

    Parameters
    ----------
    request : Request
        Trusted-origin browser request carrying the named session cookie.
    mutation : bool, default=False
        Require the session-bound CSRF token for a receipt update.

    Returns
    -------
    Principal
        Named operator authorized to read or acknowledge notifications for the
        current durable run.
    """
    principal = _named_operator(request, mutation=mutation)
    if principal.run_id is None:
        raise ServiceError("forbidden", "Notification session has no active run.", 403)
    run = request.app.state.repository.private_run(principal.run_id)
    if run["user_id"] != principal.user_id:
        raise ServiceError("forbidden", "Notification session does not own its active run.", 403)
    return principal


@router.get("/v1/viewer/notifications", response_model=NotificationList)
async def list_notifications(request: Request) -> dict[str, Any]:
    """Read currently visible unread notifications for the signed-in operator."""
    principal = _current_run_operator(request)
    return await run_in_threadpool(
        request.app.state.notifications.list_unread, principal.run_id, principal.user_id
    )


@router.post("/v1/viewer/notifications/read", response_model=NotificationList)
async def mark_notification_read(request: Request) -> dict[str, Any]:
    """Acknowledge one displayed notification using the session CSRF boundary."""
    principal = _current_run_operator(request, mutation=True)
    body = parse_json(await body_text(request))
    # Require the same idempotency boundary as other private workflow writes;
    # the receipt update itself is monotonic, so a repeated body/key is safe.
    mutation_token(request, principal, body)
    command = MarkNotificationReadRequest.model_validate(body)
    return await run_in_threadpool(
        request.app.state.notifications.mark_read,
        principal.run_id,
        principal.user_id,
        command.key,
        command.version,
    )
