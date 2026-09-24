"""Token roles and expiring run-scoped browser sessions."""

import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from fastapi import Request, WebSocket
from itsdangerous import BadData, URLSafeTimedSerializer

from metis_sim.application.errors import ServiceError
from metis_sim.settings import Settings

COOKIE = "metis_viewer"
ACTIONS = ("start", "pause", "resume", "set_speed", "stop")


@dataclass(frozen=True)
class Principal:
    """Verified internal claims, never accepted from browser-provided JSON."""

    role: str
    run_id: str | None = None
    allowed_actions: tuple[str, ...] = ()
    expires_at: float | None = None
    csrf_token: str | None = None
    public_demo: bool = False
    interactive: bool = False

    def require(
        self, roles: set[str], run_id: str | None = None, action: str | None = None
    ) -> None:
        """Enforce both role and scoped run/action authorization on every use."""
        if self.expires_at is not None and time.time() >= self.expires_at:
            raise ServiceError("session_expired", "Viewer session expired; reload the viewer.", 401)
        if self.role not in roles:
            raise ServiceError("forbidden", "This credential does not permit that operation.", 403)
        if self.role == "viewer_control":
            if run_id is not None and run_id != self.run_id:
                raise ServiceError("forbidden", "Viewer session belongs to another run.", 403)
            if action is not None and action not in self.allowed_actions:
                raise ServiceError("forbidden", "Viewer session does not permit that action.", 403)


class Auth:
    """Authenticate deployment tokens and issue restricted local demo sessions.

    Parameters
    ----------
    settings : Settings
        Deployment credentials and explicit origin allowlist.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if len(settings.session_secret) < 32:
            raise ValueError("METIS_SESSION_SECRET must contain at least 32 characters")
        tokens = [settings.operator_token, settings.consumer_token, settings.evaluator_token]
        if not all(len(token) >= 24 for token in tokens) or len(set(tokens)) != 3:
            raise ValueError(
                "Provide three distinct METIS role tokens (at least 24 characters each)"
            )
        self.serializer = URLSafeTimedSerializer(settings.session_secret, salt="metis-viewer-v1")

    def principal(self, request: Request | WebSocket) -> Principal:
        """Verify a bearer credential or authenticated HttpOnly session cookie."""
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            supplied = authorization[7:]
            for role in ("operator", "consumer", "evaluator"):
                if hmac.compare_digest(
                    supplied.encode("utf-8"),
                    getattr(self.settings, f"{role}_token").encode("utf-8"),
                ):
                    return Principal(role)
            raise ServiceError("unauthorized", "Invalid credentials.", 401)
        cookie = request.cookies.get(COOKIE)
        if cookie:
            try:
                payload = self.serializer.loads(cookie, max_age=self.settings.session_lifetime_s)
                if payload.get("role") != "viewer_control" or set(
                    payload.get("allowed_actions", [])
                ) - set(ACTIONS):
                    raise BadData("invalid claims")
                if not isinstance(payload.get("public_demo", False), bool):
                    raise BadData("invalid demo claim")
                if not isinstance(payload.get("interactive", False), bool):
                    raise BadData("invalid interactive claim")
                if payload.get("public_demo", False) and payload["allowed_actions"]:
                    raise BadData("public demo cannot control a shared run")
                if payload.get("public_demo", False) and not self.settings.public_demo:
                    raise BadData("public demo access is disabled")
                principal = Principal(
                    role="viewer_control",
                    run_id=payload["run_id"],
                    allowed_actions=tuple(payload["allowed_actions"]),
                    expires_at=payload["expires_at"],
                    csrf_token=payload["csrf_token"],
                    public_demo=payload.get("public_demo", False),
                    interactive=payload.get("interactive", False),
                )
                principal.require({"viewer_control"})
                return principal
            except (BadData, KeyError, TypeError) as error:
                raise ServiceError(
                    "unauthorized", "Invalid or expired viewer session.", 401
                ) from error
        raise ServiceError("unauthorized", "Authentication is required.", 401)

    def issue(
        self, run_id: str, *, public_demo: bool = False, interactive: bool = False
    ) -> tuple[str, Principal]:
        """Mint a fixed run-scoped capability after the caller authorizes issuance.

        Parameters
        ----------
        run_id : str
            Run authorized by an operator or explicit loopback demo bootstrap.
        public_demo : bool, default=False
            Issue a read-only session for the shared public demonstration.
        interactive : bool, default=False
            Mark a browser-owned run eligible for prepared-engine recovery.

        Returns
        -------
        tuple of str and Principal
            Signed cookie value and its expiring viewer permissions.
        """
        principal = Principal(
            "viewer_control",
            run_id,
            () if public_demo else ACTIONS,
            time.time() + self.settings.session_lifetime_s,
            secrets.token_urlsafe(32),
            public_demo,
            interactive,
        )
        claims: dict[str, Any] = dict(
            role=principal.role,
            run_id=run_id,
            allowed_actions=list(principal.allowed_actions),
            expires_at=principal.expires_at,
            csrf_token=principal.csrf_token,
            public_demo=principal.public_demo,
            interactive=principal.interactive,
        )
        return self.serializer.dumps(claims), principal

    def csrf(self, request: Request, principal: Principal) -> None:
        """Require a trusted Origin and session-bound token for browser mutations."""
        if principal.role != "viewer_control":
            return
        self.origin(request, required=True)
        token = request.headers.get("x-csrf-token", "")
        if not principal.csrf_token or not hmac.compare_digest(
            token.encode("utf-8"), principal.csrf_token.encode("utf-8")
        ):
            raise ServiceError("csrf_failed", "Viewer control requires a valid CSRF token.", 403)

    def origin(self, request: Request | WebSocket, required: bool = False) -> None:
        """Reject cross-origin session use outside the explicit deployment allowlist."""
        origin = request.headers.get("origin")
        if (required and not origin) or (origin and origin not in self.settings.origins):
            raise ServiceError("origin_forbidden", "Origin is not allowed.", 403)

    def local_bootstrap(self, request: Request) -> None:
        """Restrict unauthenticated prepared-demo issuance to explicit loopback mode."""
        self.origin(request)
        host = request.url.hostname
        peer = request.client.host if request.client else None
        if (
            not self.settings.local_demo
            or host not in {"localhost", "127.0.0.1", "::1", "testserver"}
            or peer not in {"127.0.0.1", "::1", "testclient"}
        ):
            raise ServiceError(
                "forbidden", "Demo session issuance is available only on local loopback.", 403
            )

    def public_bootstrap(self, request: Request) -> None:
        """Permit anonymous demo issuance only on an allowed HTTPS host.

        Parameters
        ----------
        request : Request
            Browser request whose host and optional Origin must be allowed.

        Raises
        ------
        ServiceError
            If public demo access is disabled or the request is untrusted.
        """
        self.origin(request)
        allowed_hosts = {
            urlsplit(origin).netloc
            for origin in self.settings.origins
            if urlsplit(origin).scheme == "https"
        }
        if (
            not self.settings.public_demo
            or not self.settings.cookie_secure
            or request.headers.get("host") not in allowed_hosts
        ):
            raise ServiceError("forbidden", "Public demo access is unavailable.", 403)
