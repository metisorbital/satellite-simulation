"""Integrated interval semantics, determinism, preview, and matched outcomes."""

from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

import numpy as np
import pytest
from metis_sim.adapters.configuration import load_configuration
from metis_sim.domain.config import SimulationConfig
from metis_sim.models.engine import SimulationEngine

ROOT = Path(__file__).resolve().parents[2]


def _config_payload() -> dict:
    config = load_configuration((ROOT / "configs/demo.yaml").read_text())
    return config.model_dump(mode="json")


def _config(payload: dict) -> SimulationConfig:
    return load_configuration(json.dumps(payload), "json")


def _short_config() -> dict:
    payload = _config_payload()
    payload["run"]["duration_s"] = 125
    payload["satellites"] = [payload["satellites"][1]]
    payload["satellites"][0]["operations"] = [
        {"start_s": 0, "end_s": 30, "mode": "safe"},
        {"start_s": 60, "end_s": 90, "mode": "payload_active"},
    ]
    payload["constellations"][0]["satellite_ids"] = ["METIS-02"]
    payload["scenario"][0]["points"] = [
        {"at_s": 60, "multiplier": 1.0},
        {"at_s": 120, "multiplier": 0.4},
    ]
    return payload


def test_initial_window_schedule_endpoint_and_midpoint_derating() -> None:
    """Check P-12 end-to-end at zero, load boundaries, and a ramp knot."""
    engine = SimulationEngine(_config(_short_config())).initialize()
    first = engine.sample(0)[0]
    assert first.battery_energy_wh == 340.0
    assert first.mode == first.interval_mode == "safe"
    assert first.sample_window_s == 0
    assert first.load_requested_w == 70.0
    boundary = engine.sample(60)[0]
    assert boundary.mode == "payload_active"
    assert boundary.interval_mode == "nominal"
    assert boundary.load_requested_w == 150.0
    assert engine.sample(61)[0].load_requested_w == 210.0
    end = engine.sample(90)[0]
    assert end.mode == "nominal"
    assert end.interval_mode == "payload_active"
    knot = engine.sample(120)[0]
    assert knot.truth.hidden_derating == pytest.approx(0.4)
    assert knot.truth.interval_derating == pytest.approx(0.405)
    assert knot.sample_window_s == 1
    assert (knot.observed_at - first.observed_at).total_seconds() == 120


def test_preview_matches_live_state_without_mutation_or_health() -> None:
    """Ensure previews reuse authoritative orbit and have no future EPS/truth data."""
    engine = SimulationEngine(_config(_short_config())).initialize()
    before = engine.sample(20)
    preview = engine.trajectory("METIS-02", 0, 125, 30)
    assert [point.tick for point in preview] == [0, 30, 60, 90, 120, 125]
    assert engine.sample(20) == before
    assert engine.initialize() is engine
    for point in preview:
        sample = engine.sample(point.tick)[0]
        assert point.position_itrf_m == sample.position_itrf_m
        assert point.velocity_itrf_m_s == sample.velocity_itrf_m_s
        assert point.observed_at == sample.observed_at
        assert not any(
            "energy" in key or "truth" in key or "derating" in key for key in asdict(point)
        )
    assert not any(
        "truth" in key or "failure" in key or "reserve" in key
        for key in before[0].public_channels()
    )


def test_engine_bindings_and_exported_snapshots_preserve_cached_state() -> None:
    """Keep samples and recorded model inputs stable across external access.

    Notes
    -----
    Rebinding configuration previously changed SOC without updating cached
    battery energy; nested provenance lists also exposed engine-owned state.
    """
    payload = _short_config()
    engine = SimulationEngine(_config(payload)).initialize()
    expected = engine.sample(20)
    expected_provenance = engine.provenance
    payload["profiles"]["leo_power_demo"]["battery"]["usable_capacity_wh"] *= 2
    replacement = _config(payload)
    for name, value in (("config", replacement), ("duration_s", 126), ("provenance", {})):
        with pytest.raises(AttributeError):
            setattr(engine, name, value)

    exported = engine.provenance
    exported["earth_model"] = "changed"
    exported_axis = exported["j2_fixed_axis_gcrs"]
    assert isinstance(exported_axis, list)
    exported_axis[0] = 42.0
    channels = expected[0].public_channels()
    position = channels["orbit.position_itrf_m"]
    assert isinstance(position, list)
    position[0] = 0.0

    assert engine.provenance == expected_provenance
    assert engine.sample(20) == expected
    with pytest.raises(ValueError, match="Tick must"):
        engine.sample(126)


def test_pacing_and_additional_satellite_cannot_change_existing_trace() -> None:
    """Check P-08 independence from requested speed and fleet iteration order."""
    original = _short_config()
    engine = SimulationEngine(_config(original)).initialize()
    reference = [engine.sample(tick)[0] for tick in range(126)]
    for speed in (1, 5):
        changed = copy.deepcopy(original)
        changed["run"]["speed"] = speed
        extra = copy.deepcopy(changed["satellites"][0])
        extra["satellite_id"] = "ADDED-00"
        extra["orbit"]["true_anomaly_deg"] = 43.0
        changed["satellites"].append(extra)
        changed["constellations"][0]["satellite_ids"].append(extra["satellite_id"])
        candidate = SimulationEngine(_config(changed)).initialize()
        for tick, expected in enumerate(reference):
            actual = next(
                sample for sample in candidate.sample(tick) if sample.satellite_id == "METIS-02"
            )
            assert actual == expected


@pytest.mark.slow
def test_full_six_hour_matched_control_and_varied_scenarios() -> None:
    """Execute P-10 healthy, baseline, milder, and delayed counterfactuals."""
    base = _config_payload()
    target = "METIS-02"
    outcomes: dict[str, dict[str, float | int | None]] = {}
    trajectories = {}
    generations = {}
    for label in ("baseline", "healthy", "milder", "delayed"):
        payload = copy.deepcopy(base)
        if label == "healthy":
            payload["scenario"] = []
        elif label == "milder":
            payload["scenario"][0]["points"][-1]["multiplier"] = 0.85
        elif label == "delayed":
            for point in payload["scenario"][0]["points"]:
                point["at_s"] += 3600
        started = perf_counter()
        engine = SimulationEngine(_config(payload)).initialize()
        target_index = next(
            index for index, sample in enumerate(engine.sample(0)) if sample.satellite_id == target
        )
        trace = [engine.sample(tick)[target_index] for tick in range(21_601)]
        last = trace[-1]
        outcomes[label] = {
            "failure_tick": last.truth.failure_tick,
            "reserve_entry_tick": last.truth.first_reserve_entry_tick,
            "minimum_soc": min(sample.battery_soc for sample in trace),
            "final_soc": last.battery_soc,
            "initialize_and_read_s": perf_counter() - started,
        }
        trajectories[label] = np.array([sample.position_itrf_m for sample in trace])
        generations[label] = np.array([sample.solar_power_w for sample in trace])
        if label == "baseline":
            assert last.truth.failure_tick is not None
            assert last.truth.first_reserve_entry_tick is not None
            assert last.truth.failure_tick - last.truth.first_reserve_entry_tick == 60
            assert trace[last.truth.failure_tick - 1].truth.failure_tick is None
            assert trace[last.truth.failure_tick].truth.failure_tick == last.truth.failure_tick
    print("P-10 matched six-hour outcomes: " + json.dumps(outcomes, sort_keys=True))
    assert outcomes["healthy"]["failure_tick"] is None
    assert outcomes["healthy"]["minimum_soc"] > 0.15
    assert outcomes["milder"]["failure_tick"] is None
    assert outcomes["milder"]["minimum_soc"] > outcomes["baseline"]["minimum_soc"]
    assert outcomes["delayed"]["failure_tick"] != outcomes["baseline"]["failure_tick"]
    for label in ("healthy", "milder", "delayed"):
        np.testing.assert_array_equal(trajectories[label], trajectories["baseline"])
    np.testing.assert_array_equal(generations["baseline"][:5401], generations["healthy"][:5401])
    failure = int(outcomes["baseline"]["failure_tick"])
    assert np.sum(generations["healthy"][:failure] - generations["baseline"][:failure]) > 0.0
