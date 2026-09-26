"""FastAPI composition root for one writer and one local mission viewer."""

import logging
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from metis_sim.adapters.cases import CaseRepository
from metis_sim.adapters.configuration import ConfigurationParsingError
from metis_sim.adapters.database import Database
from metis_sim.adapters.notifications import NotificationRepository
from metis_sim.adapters.reads import PublicReader
from metis_sim.adapters.repository import Repository
from metis_sim.adapters.shift_log import ShiftLogRepository
from metis_sim.api.auth import Auth
from metis_sim.api.cases import router as cases_router
from metis_sim.api.notifications import router as notifications_router
from metis_sim.api.openapi import install_openapi
from metis_sim.api.routes import router
from metis_sim.api.shift_log import router as shift_log_router
from metis_sim.api.visual import router as visual_router
from metis_sim.application.errors import ServiceError
from metis_sim.application.runner import Runner
from metis_sim.application.service import SimulationService
from metis_sim.logging import safe_sqlstate
from metis_sim.settings import Settings

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    setup_schema: bool = False,
    demo_at: int = 0,
    paced: bool = True,
    prepare_demo: bool = True,
) -> FastAPI:
    """Compose a single-process service with explicit injectable infrastructure.

    Parameters
    ----------
    settings : Settings, optional
        Explicit settings; otherwise load deployment environment variables.
    setup_schema : bool, default=False
        Create tables directly for isolated tests only. Production runs migrations.
    demo_at : int, default=0
        Persist authentic history to this tick before exposing a paused local demo.
    paced : bool, default=True
        Disable wall pacing only for offline validation.
    prepare_demo : bool, default=True
        Prepare the configured local demo during startup when enabled.

    Returns
    -------
    FastAPI
        ASGI application, ready for one Uvicorn worker.
    """
    settings = settings or Settings.from_env()
    auth = Auth(settings)
    database = Database(settings.database_url, settings.source_id)
    repository = Repository(database)
    cases = CaseRepository(database)
    notifications = NotificationRepository(database)
    shift_logs = ShiftLogRepository(database)

    def check_capacity() -> None:
        stats = database.storage_stats()
        if (
            stats["database_bytes"] >= settings.storage_quota_bytes
            or stats["host_free_bytes"] < settings.minimum_free_bytes
        ):
            raise ServiceError(
                "storage_capacity",
                "Storage quota or minimum host disk headroom reached; free space before a new run.",
                503,
            )
        if not database.healthy():
            raise ServiceError(
                "writer_ownership_lost",
                "Writer connection was lost; restart to recover safely.",
                503,
            )

    runner = Runner(repository, paced=paced, capacity_check=check_capacity)
    service = SimulationService(repository, runner)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        from starlette.concurrency import run_in_threadpool

        try:
            if setup_schema:
                database.create_test_schema()
            database.acquire_writer()
            shift_logs.ensure_users(
                [operator.model_dump(mode="json") for operator in auth.operators.values()]
            )
            repository.recover()
            repository.expire_terminal(days=0 if settings.public_demo else 7)
            if settings.local_demo and prepare_demo:
                await run_in_threadpool(service.prepare_demo, settings.demo_config, demo_at)
            runner.start()
            if settings.public_demo and prepare_demo and not settings.interactive_public_demo:
                await run_in_threadpool(service.ensure_public_demo, settings.demo_config)
            yield
        finally:
            await run_in_threadpool(runner.close)
            database.close()

    app = FastAPI(
        title="Metis Satellite Simulation",
        version="0.1.0",
        lifespan=lifespan,
        description="Physics simulation and recorded satellite telemetry replay. One writer; public measurements and separate private evaluation.",
    )
    for key, value in dict(
        settings=settings,
        auth=auth,
        database=database,
        repository=repository,
        cases=cases,
        notifications=notifications,
        shift_logs=shift_logs,
        reader=PublicReader(database, settings.session_secret),
        runner=runner,
        service=service,
        public_viewer_slots=threading.BoundedSemaphore(settings.public_viewer_limit),
    ).items():
        setattr(app.state, key, value)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = str(uuid4())
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as error:
            # Do not let an internal exception or rejected output projection expose
            # private values through an outer server traceback or error body.
            logger.error(
                "request_failed",
                extra={"request_id": request.state.request_id, "error_type": type(error).__name__},
            )
            response = error_response(
                request, "internal_error", "An unexpected service error occurred.", 500
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/v1"):
            response.headers["Cache-Control"] = "no-store"
        logger.info(
            "http_request",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": (time.monotonic() - started) * 1000,
            },
        )
        return response

    def error_response(
        request: Request, code: str, message: str, status: int, details: list | None = None
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content=dict(
                code=code,
                message=message,
                details=details or [],
                request_id=getattr(request.state, "request_id", str(uuid4())),
            ),
        )

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, error: ServiceError) -> JSONResponse:
        if error.status >= 500:
            logger.warning(
                "service_error",
                extra={
                    "request_id": getattr(request.state, "request_id", None),
                    "error_code": error.code,
                    "status": error.status,
                },
            )
        return error_response(request, error.code, error.message, error.status, error.details)

    @app.exception_handler(RequestValidationError)
    @app.exception_handler(ValidationError)
    async def validation_error(
        request: Request, error: RequestValidationError | ValidationError
    ) -> JSONResponse:
        details = [
            {"path": ".".join(str(part) for part in item["loc"]), "reason": item["msg"]}
            for item in error.errors()
        ]
        return error_response(
            request, "validation_failed", "Request validation failed.", 422, details
        )

    @app.exception_handler(ConfigurationParsingError)
    async def configuration_error(
        request: Request, error: ConfigurationParsingError
    ) -> JSONResponse:
        return error_response(
            request,
            "invalid_configuration",
            "Configuration could not be safely parsed.",
            422,
            [{"path": "body", "reason": "Invalid syntax, duplicate key, size, or nesting."}],
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        logger.error(
            "database_error",
            extra={
                "request_id": getattr(request.state, "request_id", None),
                "error_type": type(error).__name__,
                "sqlstate": safe_sqlstate(error),
            },
        )
        return error_response(
            request,
            "persistence_unavailable",
            "Database is unavailable; retry with the same key.",
            503,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return error_response(request, "http_error", str(error.detail), error.status_code)

    @app.exception_handler(ValueError)
    async def physics_preflight_error(request: Request, error: ValueError) -> JSONResponse:
        logger.warning("preflight_rejected", extra={"error_type": type(error).__name__})
        return error_response(
            request,
            "physics_preflight_failed",
            "Run is outside supported physics or pinned time-data coverage.",
            422,
        )

    app.include_router(router)
    app.include_router(cases_router)
    app.include_router(notifications_router)
    app.include_router(shift_log_router)
    app.include_router(visual_router)
    install_openapi(app)
    if settings.frontend_path.is_dir():
        # A root StaticFiles mount also matches WebSocket scopes. Reject unknown
        # socket paths before they reach its HTTP-only handler.
        @app.websocket("/{path:path}")
        async def reject_unknown_socket(websocket: WebSocket) -> None:
            """Reject a WebSocket request that did not match an API route.

            Parameters
            ----------
            websocket : WebSocket
                Unaccepted connection targeting an unsupported socket path.
            """
            await websocket.close(code=1008)

        app.mount("/", StaticFiles(directory=settings.frontend_path, html=True), name="viewer")
    return app
