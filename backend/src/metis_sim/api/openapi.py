"""Document strict raw-body routes using the same authoritative Pydantic models."""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel

from metis_sim.api.requests import (
    CreateRunRequest,
    ViewerConfigurationRequest,
    ViewerLoginRequest,
    ViewerSeekRequest,
    ViewerSourceRequest,
)
from metis_sim.domain.cases import (
    AssessmentCaseRequest,
    CaptureCaseEvidenceRequest,
    CreateCaseRequest,
    DecisionCaseRequest,
    OutcomeCaseRequest,
    RecommendationCaseRequest,
)
from metis_sim.domain.config import SimulationConfig
from metis_sim.domain.notifications import MarkNotificationReadRequest
from metis_sim.domain.public import ControlRequest
from metis_sim.domain.shift_log import (
    AddShiftLogEntryRequest,
    SubmitShiftLogRequest,
    UpdateShiftLogSummaryRequest,
)


def install_openapi(app: FastAPI) -> None:
    """Register body schemas while retaining duplicate-key rejection before validation."""

    def generate() -> dict:
        """Build the OpenAPI document from route metadata and strict wire contracts."""
        if app.openapi_schema is not None:
            return app.openapi_schema
        document = get_openapi(
            title=app.title, version=app.version, routes=app.routes, description=app.description
        )
        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        bodies: list[tuple[str, type[BaseModel]]] = [
            ("/v1/configurations/validate", SimulationConfig),
            ("/v1/configurations", SimulationConfig),
            ("/v1/runs", CreateRunRequest),
            ("/v1/viewer/login", ViewerLoginRequest),
            ("/v1/viewer/configuration", ViewerConfigurationRequest),
            ("/v1/viewer/source", ViewerSourceRequest),
            ("/v1/viewer/seek", ViewerSeekRequest),
            ("/v1/runs/{run_id}/control", ControlRequest),
            ("/v1/runs/{run_id}/shift-logs/entries", AddShiftLogEntryRequest),
            ("/v1/runs/{run_id}/shift-logs/{shift_id}/summary", UpdateShiftLogSummaryRequest),
            ("/v1/runs/{run_id}/shift-logs/{shift_id}/submit", SubmitShiftLogRequest),
            ("/v1/runs/{run_id}/cases", CreateCaseRequest),
            ("/v1/viewer/cases/{case_id}/assessment", AssessmentCaseRequest),
            ("/v1/viewer/cases/{case_id}/recommendation", RecommendationCaseRequest),
            ("/v1/viewer/cases/{case_id}/decision", DecisionCaseRequest),
            ("/v1/viewer/cases/{case_id}/outcome", OutcomeCaseRequest),
            ("/v1/viewer/cases/{case_id}/evidence", CaptureCaseEvidenceRequest),
            ("/v1/viewer/notifications/read", MarkNotificationReadRequest),
        ]
        for path, model in bodies:
            schema = model.model_json_schema(ref_template="#/components/schemas/{model}")
            schemas.update(schema.pop("$defs", {}))
            schemas[model.__name__] = schema
            document["paths"][path]["post"]["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{model.__name__}"}
                    }
                },
            }
            if model is SimulationConfig:
                document["paths"][path]["post"]["requestBody"]["content"]["application/yaml"] = {
                    "schema": {"type": "string"},
                    "example": "# Supply a complete simulation.v1 YAML configuration",
                }
        document["components"]["securitySchemes"] = {
            "bearer": {
                "type": "http",
                "scheme": "bearer",
                "description": "Deployment-issued operator, consumer, or evaluator token; route roles still apply.",
            },
            "viewerSession": {"type": "apiKey", "in": "cookie", "name": "metis_viewer"},
        }
        for path, methods in document["paths"].items():
            if path.startswith("/v1/") and path not in {"/v1/viewer/bootstrap", "/v1/viewer/login"}:
                for operation in methods.values():
                    if isinstance(operation, dict):
                        named_session_only = "/shift-logs" in path or "/cases" in path or "/notifications" in path
                        if (
                            path in {"/v1/viewer/session", "/v1/viewer/logout"}
                            or named_session_only
                        ):
                            operation["security"] = [{"viewerSession": []}]
                            if named_session_only:
                                record_name = "Shift Log" if "/shift-logs" in path else "notification" if "/notifications" in path else "case"
                                operation["description"] += (
                                    f"\nRequires a named operator session authorized for this {record_name}; "
                                    "shared bearer tokens and anonymous sessions are not accepted."
                                )
                                if operation.get("requestBody"):
                                    operation.setdefault("parameters", []).extend(
                                        [
                                            {
                                                "name": "Idempotency-Key",
                                                "in": "header",
                                                "required": True,
                                                "schema": {
                                                    "type": "string",
                                                    "minLength": 1,
                                                    "maxLength": 128,
                                                },
                                            },
                                            {
                                                "name": "X-CSRF-Token",
                                                "in": "header",
                                                "required": True,
                                                "schema": {"type": "string"},
                                            },
                                            {
                                                "name": "Origin",
                                                "in": "header",
                                                "required": True,
                                                "schema": {"type": "string"},
                                            },
                                        ]
                                    )
                            continue
                        operation["security"] = [{"bearer": []}]
                        if (
                            not path.startswith(
                                ("/v1/configurations", "/v1/operator/", "/v1/evaluation/")
                            )
                            and path != "/v1/runs"
                        ):
                            operation["security"].append({"viewerSession": []})
        app.openapi_schema = document
        return document

    # FastAPI explicitly supports replacing this method to customize its cached schema.
    app.openapi = generate  # type: ignore[method-assign]
