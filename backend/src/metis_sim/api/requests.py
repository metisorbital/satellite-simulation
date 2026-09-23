"""Bounded strict request decoding and durable mutation identities."""

import json
from typing import Any, Literal

from fastapi import Request
from pydantic import BaseModel, ConfigDict

from metis_sim.adapters.configuration import ConfigurationParsingError, load_configuration
from metis_sim.adapters.records import canonical_hash
from metis_sim.adapters.repository import Idempotent
from metis_sim.api.auth import Principal
from metis_sim.application.errors import ServiceError
from metis_sim.domain.config import SimulationConfig


class CreateRunRequest(BaseModel):
    """A configuration revision and independent administrative retention policy."""

    model_config = ConfigDict(extra="forbid", strict=True)
    configuration_id: str
    retain: bool = False


async def body_text(request: Request) -> str:
    """Read at most one MiB before any JSON or YAML parsing occurs."""
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 1_048_576:
            raise ServiceError("request_too_large", "Request body exceeds 1 MiB.", 422)
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ServiceError("invalid_encoding", "Request must be UTF-8.", 422) from error


async def configuration_body(request: Request) -> SimulationConfig:
    """Decode bounded operator input through the authoritative configuration schema.

    Parameters
    ----------
    request : Request
        Authorized JSON or YAML configuration request.

    Returns
    -------
    SimulationConfig
        Validated immutable configuration.

    Raises
    ------
    ConfigurationParsingError
        If parsing or recursive normalization exceeds supported input limits.
    """
    content = await body_text(request)
    encoding: Literal["yaml", "json"] = (
        "yaml" if "yaml" in request.headers.get("content-type", "") else "json"
    )
    try:
        return load_configuration(content, encoding)
    except RecursionError as error:
        raise ConfigurationParsingError("Configuration exceeds parser nesting limits") from error


def parse_json(content: str) -> dict[str, Any]:
    """Reject duplicate JSON keys and non-finite values before schema validation."""

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for name, value in items:
            if name in result:
                raise ServiceError("invalid_json", "JSON contains duplicate keys.", 422)
            result[name] = value
        return result

    def invalid(_: str) -> None:
        raise ServiceError("invalid_json", "JSON numbers must be finite.", 422)

    try:
        value = json.loads(content, object_pairs_hook=pairs, parse_constant=invalid)
    except (ValueError, RecursionError) as error:
        raise ServiceError(
            "invalid_json", "Request is not a valid bounded JSON object.", 422
        ) from error
    if not isinstance(value, dict):
        raise ServiceError("invalid_json", "Request must be a JSON object.", 422)
    return value


def mutation_token(request: Request, principal: Principal, body: Any) -> Idempotent:
    """Bind an idempotency key to source, role, run, route and canonical request."""
    key = request.headers.get("idempotency-key", "")
    if not 1 <= len(key) <= 128 or not key.isascii():
        raise ServiceError(
            "idempotency_key_required", "Provide an ASCII Idempotency-Key of 1–128 characters.", 422
        )
    scope = f"{request.app.state.settings.source_id}:{principal.role}:{principal.run_id or '*'}:{request.method}:{request.url.path}"
    return scope, key, canonical_hash(body)
