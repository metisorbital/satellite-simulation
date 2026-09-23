"""Preserve nominal cadence without replaying wall-time debt after slow storage."""

from unittest.mock import Mock

import pytest
from metis_sim.adapters.repository import Repository
from metis_sim.application.runner import PreparedRun, Runner
from sqlalchemy.exc import OperationalError


def _paced_runner(speed=20):
    repository = Mock(spec=Repository)
    wall = [0.0]

    def wait(event, timeout):
        wall[0] += timeout
        return event.is_set()

    def commit(status, *args):
        wall[0] += 0.03
        return status

    repository.commit.side_effect = commit
    runner = Runner(repository, monotonic=lambda: wall[0], wait=wait)
    prepared = Mock(spec=PreparedRun)
    prepared.engine = Mock()
    prepared.engine.sample.side_effect = lambda tick: tick
    prepared.projector = Mock()
    prepared.projector.project.side_effect = lambda tick: (
        [{"observed_at": "2026-01-01T00:00:00Z", "sequence": tick}],
        [],
        [],
    )
    runner.prepared["run"] = prepared
    status = {
        "run_id": "run",
        "committed_tick": -1,
        "duration_s": 1000,
        "requested_speed": speed,
        "effective_speed": 0,
        "satellites": [{}],
    }
    return runner, status, wall


@pytest.mark.parametrize("speed", [1, 5, 20])
def test_scheduler_jitter_does_not_accumulate_or_change_tick_batches(speed):
    """Small late wake-ups preserve all fixed ticks on the nominal wall cadence."""
    runner, status, wall = _paced_runner(speed)
    count = min(4, max(1, speed // 5))
    for _ in range(50):
        wall[0] = runner._next_due + 0.007
        runner._advance(status)
    assert runner._next_due == pytest.approx(50 * count / speed)
    samples = runner.prepared["run"].engine.sample.call_args_list
    assert [call.args[0] for call in samples] == list(range(50 * count))
    commits = runner.repository.commit.call_args_list
    assert len(commits) == 50
    assert all(len(call.args[1]) == count for call in commits)


@pytest.mark.parametrize("interruption", ["status_read", "commit_retry", "slow_commit"])
def test_storage_delay_reanchors_without_immediate_catch_up(interruption):
    """Recovery waits a fresh batch period while retaining every computed tick."""
    runner, status, wall = _paced_runner()
    commit = runner.repository.commit.side_effect
    if interruption == "status_read":
        runner.repository.status.side_effect = [
            OperationalError("injected read outage", {}, None),
            status,
        ]
        runner._retry_persistence(lambda: runner.repository.status("run"), "run")
    else:
        attempts = 0

        def delayed_commit(*args):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                if interruption == "commit_retry":
                    raise OperationalError("injected write outage", {}, None)
                wall[0] += 0.25
            return commit(*args)

        runner.repository.commit.side_effect = delayed_commit
    runner._advance(status)
    recovered = wall[0]
    assert status["committed_tick"] == 3
    assert runner._next_due == pytest.approx(recovered + 0.2)
    assert not runner.backpressure
    runner._advance(status)
    assert status["committed_tick"] == 3
    wall[0] = runner._next_due
    runner._advance(status)
    assert status["committed_tick"] == 7
    samples = runner.prepared["run"].engine.sample.call_args_list
    assert [call.args[0] for call in samples] == list(range(8))
    assert runner._next_due == pytest.approx(recovered + 0.4)
