"""Strict YAML and JSON ingestion, normalization, and hashing."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Literal

import rfc8785
import yaml
from yaml.events import AliasEvent

from metis_sim.domain.config import SimulationConfig

MAX_CONFIGURATION_BYTES = 1_048_576
MAX_YAML_ALIASES = 64
MAX_EXPANDED_NODES = 100_000
MAX_NESTING_DEPTH = 64


class ConfigurationParsingError(ValueError):
    """Raised when the serialized input is invalid or unsafe to parse."""


class _DuplicateKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate keys at every mapping depth."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        """Construct a mapping while refusing duplicate keys.

        Parameters
        ----------
        node : yaml.MappingNode
            Parsed YAML mapping node.
        deep : bool, default=False
            PyYAML recursive construction flag.

        Returns
        -------
        dict[Any, Any]
            Constructed mapping with unique keys.
        """
        self.flatten_mapping(node)
        mapping: dict[Any, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                duplicate = key in mapping
            except TypeError as exc:
                raise ConfigurationParsingError("YAML mapping keys must be scalar values") from exc
            if duplicate:
                raise ConfigurationParsingError(f"duplicate YAML mapping key: {key!r}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _reject_duplicate_json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object and reject repeated property names."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigurationParsingError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_non_finite_json(value: str) -> None:
    """Reject JavaScript JSON parser extensions for NaN and Infinity."""
    raise ConfigurationParsingError(f"non-finite JSON number is forbidden: {value}")


def _walk_expanded(value: object, *, depth: int = 0, state: dict[str, Any] | None = None) -> None:
    """Bound expanded YAML node count and reject recursive aliases."""
    if state is None:
        state = {"count": 0, "active": set()}
    state["count"] += 1
    if state["count"] > MAX_EXPANDED_NODES:
        raise ConfigurationParsingError("YAML alias expansion exceeds the node limit")
    if depth > MAX_NESTING_DEPTH:
        raise ConfigurationParsingError("configuration nesting exceeds the depth limit")
    if isinstance(value, (dict, list, tuple)):
        identity = id(value)
        if identity in state["active"]:
            raise ConfigurationParsingError("recursive YAML aliases are forbidden")
        state["active"].add(identity)
        items = value.items() if isinstance(value, dict) else enumerate(value)
        for key, item in items:
            _walk_expanded(key, depth=depth + 1, state=state)
            _walk_expanded(item, depth=depth + 1, state=state)
        state["active"].remove(identity)


def _convert_sequences(value: object) -> object:
    """Convert parser sequences to tuples for strict immutable Pydantic fields."""
    if isinstance(value, dict):
        return {key: _convert_sequences(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_convert_sequences(item) for item in value)
    return value


def _parse_epoch(value: dict[str, Any]) -> None:
    """Parse ISO epoch text to datetime so strict Python validation can apply."""
    run = value.get("run")
    if not isinstance(run, dict):
        return
    epoch = run.get("epoch_utc")
    if isinstance(epoch, str):
        try:
            run["epoch_utc"] = datetime.fromisoformat(epoch.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ConfigurationParsingError("run.epoch_utc must be an ISO 8601 timestamp") from exc


def load_configuration(
    content: str,
    format: Literal["yaml", "json"] = "yaml",
) -> SimulationConfig:
    """Parse and validate YAML or JSON configuration through one strict model.

    Parameters
    ----------
    content : str
        Serialized configuration text, limited to one mebibyte in UTF-8.
    format : {'yaml', 'json'}, default='yaml'
        Input encoding to parse.

    Returns
    -------
    SimulationConfig
        Immutable Pydantic-validated configuration.

    Raises
    ------
    ConfigurationParsingError
        If the encoding is malformed, unsafe, duplicated, too large, or uses
        excessive YAML aliases.
    pydantic.ValidationError
        If a parsed object violates the versioned configuration contract.
    """
    if not isinstance(content, str):
        raise TypeError("content must be a string")
    if len(content.encode("utf-8")) > MAX_CONFIGURATION_BYTES:
        raise ConfigurationParsingError("configuration exceeds the 1 MiB limit")
    if format not in {"yaml", "json"}:
        raise ValueError("format must be 'yaml' or 'json'")
    try:
        if format == "json":
            raw = json.loads(
                content,
                object_pairs_hook=_reject_duplicate_json_pairs,
                parse_constant=_reject_non_finite_json,
            )
        else:
            alias_count = sum(isinstance(event, AliasEvent) for event in yaml.parse(content))
            if alias_count > MAX_YAML_ALIASES:
                raise ConfigurationParsingError("YAML alias count exceeds the limit")
            raw = yaml.load(content, Loader=_DuplicateKeySafeLoader)
    except ConfigurationParsingError:
        raise
    except (yaml.YAMLError, json.JSONDecodeError, UnicodeError) as exc:
        raise ConfigurationParsingError(f"invalid {format.upper()} configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationParsingError("configuration root must be an object")
    if format == "yaml":
        _walk_expanded(raw)
    _parse_epoch(raw)
    return SimulationConfig.model_validate(_convert_sequences(raw), strict=True)


def normalize_configuration(config: SimulationConfig) -> dict[str, Any]:
    """Materialize defaults, sort keyed objects, and embed resolved profiles.

    Parameters
    ----------
    config : SimulationConfig
        Validated immutable input configuration.

    Returns
    -------
    dict[str, Any]
        JSON-compatible canonical projection for storage and hashing.
    """
    if not isinstance(config, SimulationConfig):
        raise TypeError("config must be a SimulationConfig")
    result = config.model_dump(mode="json", exclude_none=False)
    result["run"]["epoch_utc"] = result["run"]["epoch_utc"].replace("+00:00", "Z")
    result["profiles"] = {key: result["profiles"][key] for key in sorted(result["profiles"])}
    satellites = []
    for satellite in sorted(result["satellites"], key=lambda item: item["satellite_id"]):
        normalized = dict(satellite)
        normalized["operations"] = sorted(
            normalized["operations"], key=lambda item: (item["start_s"], item["end_s"])
        )
        normalized["resolved_profile"] = result["profiles"][satellite["profile_id"]]
        satellites.append(normalized)
    result["satellites"] = satellites
    result["constellations"] = sorted(
        (
            {**item, "satellite_ids": sorted(item["satellite_ids"])}
            for item in result["constellations"]
        ),
        key=lambda item: item["constellation_id"],
    )
    result["scenario"] = sorted(result["scenario"], key=lambda item: item["satellite_id"])
    result["normalization"] = {
        "algorithm": "simulation-normalization.v1",
        "canonical_json": "RFC8785",
    }
    return result


def configuration_hash(config: SimulationConfig) -> str:
    """Return the SHA-256 digest of normalized RFC 8785 canonical JSON.

    Parameters
    ----------
    config : SimulationConfig
        Validated immutable input configuration.

    Returns
    -------
    str
        Lowercase hexadecimal SHA-256 digest.
    """
    import hashlib

    canonical = rfc8785.dumps(normalize_configuration(config))
    return hashlib.sha256(canonical).hexdigest()


__all__ = [
    "ConfigurationParsingError",
    "configuration_hash",
    "load_configuration",
    "normalize_configuration",
]
