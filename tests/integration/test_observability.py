"""Structured operational signals and redaction boundaries."""

import json
import logging
from unittest.mock import Mock

from metis_sim.adapters.repository import Repository
from metis_sim.application.errors import ServiceError
from metis_sim.application.runner import Runner
from metis_sim.logging import OperationalFormatter, safe_sqlstate


def test_operational_formatter_allows_metrics_and_redacts_unlisted_values():
    """Serialize approved metrics without carrying a private record attribute."""
    record = logging.LogRecord(
        "metis_sim.application.runner", logging.INFO, __file__, 0, "batch_committed", (), None
    )
    record.run_id = "run-1"
    record.processing_ms = 12.5
    record.sqlstate = "57014"
    record.resync_count = 2
    record.private_payload = "PRIVATE_LOG_SENTINEL"

    rendered = OperationalFormatter().format(record)
    payload = json.loads(rendered)

    assert payload["run_id"] == "run-1"
    assert payload["processing_ms"] == 12.5
    assert payload["sqlstate"] == "57014"
    assert payload["resync_count"] == 2
    assert "PRIVATE_LOG_SENTINEL" not in rendered


def test_safe_sqlstate_exposes_only_valid_database_codes():
    """Keep PostgreSQL's stable error category without its driver message."""

    class Origin:
        """Expose one driver-native SQLSTATE for the adapter boundary."""

        sqlstate = "57014"

    class DatabaseFailure(Exception):
        """Carry the driver-native error without a serialized exception message."""

        orig = Origin()

    assert safe_sqlstate(DatabaseFailure("PRIVATE_LOG_SENTINEL")) == "57014"
    assert safe_sqlstate(Exception("PRIVATE_LOG_SENTINEL")) is None


def test_http_request_log_contains_trace_without_authorization_header(client, caplog):
    """Emit an INFO request completion record with a response-correlated trace ID."""
    caplog.set_level(logging.INFO, logger="metis_sim.api.app")
    response = client.get("/v1/catalog", headers={"Authorization": "Bearer PRIVATE_LOG_SENTINEL"})

    assert response.status_code == 401
    record = next(record for record in caplog.records if record.message == "http_request")
    assert record.request_id == response.headers["X-Request-ID"]
    assert record.method == "GET"
    assert record.path == "/v1/catalog"
    assert record.status == 401
    assert "PRIVATE_LOG_SENTINEL" not in caplog.text


def test_runner_failure_logs_safe_diagnostic_and_persists_it(caplog):
    """Preserve a controlled storage diagnostic without logging its private message."""
    repository = Mock(spec=Repository)
    status = {
        "run_id": "run-1",
        "status": "running",
        "committed_tick": 41,
        "requested_speed": 20,
    }
    committed = []

    def record_commit(state, *_):
        """Capture the sanitized status committed by the failure boundary."""
        committed.append(state.copy())
        return state

    repository.status.return_value = status
    repository.final_truth.return_value = []
    repository.commit.side_effect = record_commit
    runner = Runner(repository)
    runner.active_id = "run-1"
    caplog.set_level(logging.INFO, logger="metis_sim.application.runner")

    runner._fail(ServiceError("storage_capacity", "PRIVATE_LOG_SENTINEL", 503))

    record = next(record for record in caplog.records if record.message == "runner_failed")
    assert record.run_id == "run-1"
    assert record.tick == 41
    assert record.status == "running"
    assert record.error_code == "storage_capacity"
    assert committed[-1]["status"] == "failed"
    assert committed[-1]["diagnostic"] == "storage_capacity"
    assert "PRIVATE_LOG_SENTINEL" not in caplog.text
