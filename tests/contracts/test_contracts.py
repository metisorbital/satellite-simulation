"""Contract validation tests against normative fixture and wire examples."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from metis_sim.adapters.configuration import (
    ConfigurationParsingError,
    configuration_hash,
    load_configuration,
    normalize_configuration,
)
from metis_sim.domain.public import PublicRunStatus
from metis_sim.domain.telemetry import MeasurementFrame, OperationalEvent
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
INVALID = Path(__file__).parent / "fixtures" / "invalid"


def test_demo_and_matched_healthy_configs_validate_and_hash_differently() -> None:
    """Validate the three-satellite scenario and its healthy matched fixture."""
    demo = load_configuration((ROOT / "configs/demo.yaml").read_text())
    healthy = load_configuration((ROOT / "configs/healthy-matched.yaml").read_text())

    assert [item.satellite_id for item in demo.satellites] == ["METIS-01", "METIS-02", "METIS-03"]
    assert demo.scenario[0].satellite_id == "METIS-02"
    assert healthy.scenario == ()
    assert configuration_hash(demo) != configuration_hash(healthy)


@pytest.mark.parametrize("fixture", sorted(INVALID.glob("*.yaml")) + sorted(INVALID.glob("*.json")))
def test_golden_invalid_configurations_are_rejected(fixture: Path) -> None:
    """Reject every committed malformed, unsafe, or semantically invalid fixture."""
    serialized = fixture.read_text()
    encoding = "json" if fixture.suffix == ".json" else "yaml"
    with pytest.raises((ConfigurationParsingError, ValidationError)):
        load_configuration(serialized, format=encoding)


def test_normalization_resolves_profiles_and_orders_keyed_collections() -> None:
    """Resolve immutable spacecraft profiles and deterministic keyed ordering."""
    config = load_configuration((ROOT / "configs/demo.yaml").read_text())
    normalized = normalize_configuration(config)

    assert normalized["satellites"][0]["satellite_id"] == "METIS-01"
    assert normalized["satellites"][0]["resolved_profile"]["battery"]["usable_capacity_wh"] == 400.0
    assert normalized["normalization"]["canonical_json"] == "RFC8785"
    with pytest.raises(TypeError, match="immutable"):
        config.profiles["leo_power_demo"] = config.profiles["leo_power_demo"]


def test_hash_does_not_depend_on_satellite_input_order() -> None:
    """Sort keyed satellite objects before computing the reproducibility hash."""
    source = yaml.safe_load((ROOT / "configs/demo.yaml").read_text())
    source["satellites"] = list(reversed(source["satellites"]))
    reordered = load_configuration(yaml.safe_dump(source, sort_keys=False))
    original = load_configuration((ROOT / "configs/demo.yaml").read_text())

    assert configuration_hash(reordered) == configuration_hash(original)


def test_json_and_yaml_use_the_same_validation_and_hash_path() -> None:
    """Normalize equivalent JSON and YAML inputs to an identical digest."""
    source = yaml.safe_load((ROOT / "configs/demo.yaml").read_text())
    yaml_config = load_configuration(yaml.safe_dump(source, sort_keys=False))
    json_config = load_configuration(json.dumps(source), format="json")

    assert configuration_hash(yaml_config) == configuration_hash(json_config)


def test_timestamp_offsets_are_normalized_to_utc() -> None:
    """Normalize equivalent run epochs expressed with different UTC offsets."""
    source = yaml.safe_load((ROOT / "configs/healthy-matched.yaml").read_text())
    offset_source = json.loads(json.dumps(source))
    offset_source["run"]["epoch_utc"] = "2026-09-21T03:00:00+03:00"

    utc_config = load_configuration(json.dumps(source), format="json")
    offset_config = load_configuration(json.dumps(offset_source), format="json")

    assert utc_config.run.epoch_utc.isoformat() == "2026-09-21T00:00:00+00:00"
    assert configuration_hash(utc_config) == configuration_hash(offset_config)


def test_observed_source_frame_has_no_run_dependency() -> None:
    """Accept an observed-source frame with no simulator-only run identifier."""
    frame = MeasurementFrame.model_validate_json(
        (Path(__file__).parent / "fixtures/observed-source.json").read_text()
    )

    assert frame.source_kind == "observed"
    assert "run_id" not in MeasurementFrame.model_fields
    assert frame.channels["eps.solar_power_w"].quality == "missing"


@pytest.mark.parametrize(
    "private_field",
    ["scenario", "seed", "hidden_multiplier", "reserve_soc", "configuration_hash"],
)
def test_public_run_provenance_rejects_private_manifest_fields(private_field: str) -> None:
    """Reject private metadata even when supplied through public provenance.

    Parameters
    ----------
    private_field : str
        Private manifest or scenario metadata attempting to cross the boundary.
    """
    provenance: dict[str, str | bool] = {
        "orbit_model": "j2_cartesian",
        "coverage_validated": True,
    }
    status = {
        "run_id": "8152b6ac-8f6c-4d54-94eb-764b414a1b9c",
        "status": "created",
        "epoch_utc": "2026-09-21T00:00:00Z",
        "duration_s": 60,
        "requested_speed": 20,
        "satellites": [],
        "model_provenance": provenance,
    }
    public = PublicRunStatus.model_validate_json(json.dumps(status))
    assert public.model_dump(mode="json")["model_provenance"] == status["model_provenance"]

    provenance[private_field] = "private"
    with pytest.raises(ValidationError) as error:
        PublicRunStatus.model_validate_json(json.dumps(status))
    assert error.value.errors()[0]["loc"] == ("model_provenance", private_field)
    assert error.value.errors()[0]["type"] == "extra_forbidden"


def test_measurement_frame_rejects_unknown_channel_and_nonfinite_value() -> None:
    """Prevent arbitrary channel injection and non-finite public JSON values."""
    fixture = json.loads((Path(__file__).parent / "fixtures/observed-source.json").read_text())
    fixture["channels"]["secret.fault_multiplier"] = {"value": 0.1, "quality": "valid"}
    with pytest.raises(ValidationError):
        MeasurementFrame.model_validate(fixture)
    fixture["channels"].pop("secret.fault_multiplier")
    fixture["channels"]["eps.battery_soc"] = {"value": float("nan"), "quality": "valid"}
    with pytest.raises(ValidationError):
        MeasurementFrame.model_validate(fixture)
    fixture["channels"]["eps.battery_soc"] = {"value": 0.7, "quality": "valid"}
    fixture["sample_window_s"] = float("inf")
    with pytest.raises(ValidationError):
        MeasurementFrame.model_validate(fixture)


@pytest.mark.parametrize(
    ("event_type", "details"),
    [
        ("mode_changed", {"from_mode": "nominal", "to_mode": "safe"}),
        (
            "low_energy_limit_entered",
            {"channel_id": "eps.battery_soc", "operator": "lt", "value": 0.2, "clear_value": 0.25},
        ),
        ("power_unserved", {"active": True, "value_w": 12.5, "sample_window_s": 1}),
    ],
)
def test_operational_event_uses_exact_allowlisted_details(
    event_type: str, details: dict[str, object]
) -> None:
    """Accept supported observable event detail envelopes."""
    event = OperationalEvent.model_validate_json(
        json.dumps(
            {
                "schema_version": "operational_event.v1",
                "source_id": "metis-simulator-local",
                "stream_id": "8152b6ac-8f6c-4d54-94eb-764b414a1b9c",
                "event_sequence": 1,
                "satellite_id": "METIS-01",
                "source_kind": "synthetic",
                "time_domain": "simulation_utc",
                "observed_at": "2026-09-21T00:01:00Z",
                "emitted_at": "2026-09-21T00:01:01Z",
                "event_type": event_type,
                "reason_code": "condition_changed",
                "details": details,
            }
        )
    )

    assert event.event_type == event_type


def test_operational_event_rejects_private_or_unknown_details() -> None:
    """Keep scenario causes and arbitrary fields out of the public event schema."""
    event_data = {
        "schema_version": "operational_event.v1",
        "source_id": "metis-simulator-local",
        "stream_id": "8152b6ac-8f6c-4d54-94eb-764b414a1b9c",
        "event_sequence": 0,
        "satellite_id": "METIS-01",
        "source_kind": "synthetic",
        "time_domain": "simulation_utc",
        "observed_at": "2026-09-21T00:00:00Z",
        "emitted_at": "2026-09-21T00:00:00Z",
        "event_type": "mode_changed",
        "reason_code": "schedule",
        "details": {"from_mode": "nominal", "to_mode": "safe", "injection_started": True},
    }

    with pytest.raises(ValidationError):
        OperationalEvent.model_validate_json(json.dumps(event_data))
