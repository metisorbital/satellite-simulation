"""Private evaluation and public operational interval boundary tests."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
from metis_sim.models.operations import operational_mode
from metis_sim.models.scenarios import ReserveEvaluator, derating_multipliers


def test_half_open_schedule_and_adjacent_modes() -> None:
    """Check exact ticks including sequence-zero commands and reversion."""
    operations = [
        SimpleNamespace(start_s=0, end_s=60, mode="safe"),
        SimpleNamespace(start_s=60, end_s=120, mode="payload_active"),
    ]
    assert operational_mode(0, "nominal", operations) == "safe"
    assert operational_mode(59, "nominal", operations) == "safe"
    assert operational_mode(60, "nominal", operations) == "payload_active"
    assert operational_mode(119, "nominal", operations) == "payload_active"
    assert operational_mode(120, "nominal", operations) == "nominal"


def test_ramp_uses_true_midpoint_and_holds_end_values() -> None:
    """Check P-12 interpolation at, before, and after a control-point tick."""
    points = [SimpleNamespace(at_s=60, multiplier=1.0), SimpleNamespace(at_s=120, multiplier=0.4)]
    times = np.array([0.0, 59.5, 60.0, 60.5, 90.0, 119.5, 120.0, 120.5])
    expected = [1.0, 1.0, 1.0, 0.995, 0.7, 0.405, 0.4, 0.4]
    np.testing.assert_allclose(derating_multipliers(times, points), expected, atol=1e-15)


def test_reserve_dwell_is_continuous_state_driven_and_latched() -> None:
    """Record first entry separately and reset incomplete dwell on equality."""
    evaluator = ReserveEvaluator(reserve_soc=0.15, dwell_s=60)
    evaluator.evaluate(0, 0.14)
    assert evaluator.first_entry_tick == 0
    assert evaluator.failure_tick is None
    for tick in range(1, 30):
        evaluator.evaluate(tick, 0.14)
    evaluator.evaluate(30, 0.15)
    assert evaluator.active_entry_tick is None
    for tick in range(31, 91):
        evaluator.evaluate(tick, 0.14)
    assert evaluator.failure_tick is None
    evaluator.evaluate(91, 0.14)
    assert evaluator.first_entry_tick == 0
    assert evaluator.active_entry_tick == 31
    assert evaluator.failure_tick == 91
    evaluator.evaluate(92, 0.9)
    assert evaluator.failure_tick == 91
    assert evaluator.active_entry_tick is None
