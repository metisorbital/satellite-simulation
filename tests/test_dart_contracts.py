"""Regression checks for Pydantic-derived Dart wire contracts."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_contracts", ROOT / "scripts/generate_contracts.py"
)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


def test_generated_contracts_are_current_and_public() -> None:
    """Keep checked-in output deterministic and free of private configuration."""
    source = GENERATOR.render_dart(GENERATOR.public_definitions())
    assert source == (ROOT / "frontend/lib/api/generated.dart").read_text()
    assert "class SimulationConfig" not in source
    assert "class Scenario" not in source
    assert "class ViewerBootstrap" in source
    assert "class Snapshot" in source
    assert "final List<double> position_itrs_m" in source
    assert "final Map<String, ChannelReading> channels" in source
    assert "final Object? value" in source


def test_nested_and_nullable_models_preserve_wire_shape() -> None:
    """Generate typed nested conversion and preserve explicit response nulls."""
    source = GENERATOR.render_dart(GENERATOR.public_definitions())
    assert "ViewerBootstrap.fromJson(Map<String, dynamic> json)" in source
    assert "'run': run.toJson()" in source
    assert "'committed_at': committed_at == null ? null : committed_at!" in source
    assert "if (frame != null) 'frame': frame!" in source
    assert "'channels': channels.map((key, item) => MapEntry(key, item.toJson()))" in source


def test_generation_does_not_need_node_and_retains_schema_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generate all artifacts without invoking a frontend toolchain."""
    monkeypatch.setattr(GENERATOR, "SCHEMA_DIR", tmp_path / "schemas")
    monkeypatch.setattr(GENERATOR, "DART_OUTPUT", tmp_path / "generated.dart")
    GENERATOR.main()
    first = (tmp_path / "generated.dart").read_bytes()
    GENERATOR.main()
    assert (tmp_path / "generated.dart").read_bytes() == first
    generated_schema = json.loads((tmp_path / "schemas/public-api.v1.schema.json").read_text())
    checked_in = json.loads((ROOT / "schemas/public-api.v1.schema.json").read_text())
    assert generated_schema == checked_in
    assert "SimulationConfig" in generated_schema["$defs"]


def test_unknown_schema_vocabulary_fails_instead_of_silently_erasing_types() -> None:
    """Require deliberate support when contracts gain new schema shapes."""
    with pytest.raises(ValueError, match="Unsupported public schema"):
        GENERATOR.render_dart({"NewModel": {"properties": {"value": {"oneOf": []}}}})


def test_dart_runtime_roundtrip(tmp_path: Path) -> None:
    """Execute generated models against real telemetry and nullable unions.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Isolated directory for the standalone Dart verification program.
    """
    import os
    import shutil
    import subprocess

    executable = os.environ.get("DART_EXECUTABLE") or shutil.which("dart")
    if not executable:
        pytest.skip("Dart SDK unavailable; CI runs this check with Flutter on PATH")
    fixture = json.loads((ROOT / "tests/contracts/fixtures/observed-source.json").read_text())
    status = GENERATOR.PublicRunStatus(
        run_id="run",
        status="created",
        epoch_utc="2026-01-01T00:00:00Z",
        duration_s=60,
        requested_speed=1,
        satellites=[],
        model_provenance={"frame": "ITRS"},
    ).model_dump(mode="json")
    snapshot = {"status": status, "frames": [fixture]}
    program = tmp_path / "roundtrip.dart"
    contract_uri = (ROOT / "frontend/lib/api/generated.dart").as_uri()
    program.write_text(
        f"import '{contract_uri}';\n"
        "import 'dart:convert';\n"
        "void main() {\n"
        f"  final snapshot = jsonDecode(r'''{json.dumps(snapshot)}''') as Map<String, dynamic>;\n"
        "  print(jsonEncode(Snapshot.fromJson(snapshot).toJson()));\n"
        f"  final frame = jsonDecode(r'''{json.dumps(fixture)}''') as Map<String, dynamic>;\n"
        "  final result = MeasurementFrame.fromJson(frame).toJson();\n"
        "  if (jsonEncode(result) != jsonEncode(frame)) {\n"
        "    // Map order is not semantically significant.\n"
        "    for (final key in frame.keys) {\n"
        "      if (result[key] is num && frame[key] is num && result[key] == frame[key]) continue;\n"
        "      if (jsonEncode(result[key]) != jsonEncode(frame[key])) throw StateError(key);\n"
        "    }\n"
        "  }\n"
        "  for (final value in [null, 1.5, [1.0, 2.0, 3.0]]) {\n"
        "    final reading = {'value': value, 'quality': value == null ? 'missing' : 'valid'};\n"
        "    if (jsonEncode(ChannelReading.fromJson(reading).toJson()) != jsonEncode(reading)) {\n"
        "      throw StateError('channel roundtrip');\n"
        "    }\n"
        "  }\n"
        "  final event = <String, dynamic>{\n"
        "    'schema_version': 'operational_event.v1', 'source_id': 'source',\n"
        "    'stream_id': 'stream', 'event_sequence': 0, 'satellite_id': 'sat',\n"
        "    'source_kind': 'synthetic', 'time_domain': 'simulation_utc',\n"
        "    'observed_at': '2026-01-01T00:00:00Z', 'emitted_at': '2026-01-01T00:00:00Z',\n"
        "    'event_type': 'power_unserved', 'reason_code': 'limit',\n"
        "    'details': {'active': true, 'value_w': 2.0, 'sample_window_s': 1.0},\n"
        "  };\n"
        "  if (jsonEncode(OperationalEvent.fromJson(event).toJson()) != jsonEncode(event)) {\n"
        "    throw StateError('event roundtrip');\n"
        "  }\n"
        "}\n"
    )
    result = subprocess.run(
        [executable, "run", str(program)], check=True, capture_output=True, text=True
    )
    assert json.loads(result.stdout) == snapshot
