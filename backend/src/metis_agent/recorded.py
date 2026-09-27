"""Source-time alignment for the saved BUPT-1 model prediction."""

from datetime import UTC, datetime, timedelta

from metis_agent.briefing import Decision, _load_artifact, build_decision


def recorded_mission_epoch() -> datetime:
    """Return the saved forecast mission origin in interpreted source UTC.

    Returns
    -------
    datetime
        Forecast origin plus its command lead, with UTC timezone.
    """
    artifact, _ = _load_artifact()
    origin = datetime.fromisoformat(artifact["source"]["decision_time"]).replace(tzinfo=UTC)
    return origin + timedelta(minutes=float(artifact["lead_minutes"]))


def build_recorded_decision() -> Decision:
    """Build the unchanged planner decision aligned to recorded source time.

    Returns
    -------
    Decision
        Saved model predictions and assumed mission planning scenario.
    """
    return build_decision(
        recorded_mission_epoch().isoformat().replace("+00:00", "Z"),
        "BUPT-1 recorded telemetry; saved model forecast with assumed mission power scaling",
    )
