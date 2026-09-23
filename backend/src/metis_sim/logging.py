"""Structured operational logging without scenario or credential payloads."""

import json
import logging
from datetime import UTC, datetime

FIELDS = (
    "run_id",
    "tick",
    "frame_count",
    "commit_ms",
    "processing_ms",
    "queue_depth",
    "requested_speed",
    "effective_speed",
    "error_type",
    "error_code",
    "sqlstate",
    "diagnostic",
    "resync_count",
    "request_id",
    "method",
    "path",
    "status",
    "duration_ms",
)


def safe_sqlstate(error: BaseException) -> str | None:
    """Extract a PostgreSQL SQLSTATE without retaining a database message.

    Parameters
    ----------
    error : BaseException
        Database exception that may expose a driver-native error as ``orig``.

    Returns
    -------
    str or None
        A five-character alphanumeric SQLSTATE, or ``None`` when unavailable.
    """
    origin = getattr(error, "orig", None)
    value = getattr(origin, "sqlstate", None) or getattr(origin, "pgcode", None)
    if isinstance(value, str) and len(value) == 5 and value.isalnum():
        return value.upper()
    return None


class OperationalFormatter(logging.Formatter):
    """Serialize an explicit operational field allowlist as one JSON record."""

    def format(self, record: logging.LogRecord) -> str:
        """Return a structured line without arbitrary extras or exception arguments."""
        payload = {
            "at": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update({name: getattr(record, name) for name in FIELDS if hasattr(record, name)})
        return json.dumps(payload, allow_nan=False)


def configure_logging() -> None:
    """Configure the application logger without altering third-party log handlers."""
    logger = logging.getLogger("metis_sim")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(OperationalFormatter())
    logger.handlers[:] = [handler]
    logger.propagate = False
