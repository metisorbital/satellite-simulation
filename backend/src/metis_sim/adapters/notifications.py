"""Server-derived operator notifications and durable read receipts."""

import json
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from metis_sim.adapters import tables
from metis_sim.adapters.database import Database
from metis_sim.adapters.records import canonical_hash, utc_now
from metis_sim.application.errors import ServiceError
from metis_sim.domain.telemetry import MeasurementFrame


class NotificationRepository:
    """Derive public warning notifications and persist operator acknowledgements.

    Parameters
    ----------
    database : Database
        Existing database and serialized writer transaction provider.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _warnings(run_id: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert latest committed public envelopes into workspace warning rows."""
        warnings: list[dict[str, Any]] = []
        for row in rows:
            frame = MeasurementFrame.model_validate_json(
                json.dumps(row["payload"], ensure_ascii=False, separators=(",", ":"))
            )
            qualities: dict[str, list[str]] = {}
            for channel_id, reading in frame.channels.items():
                if reading.quality in {"missing", "invalid", "saturated"}:
                    qualities.setdefault(reading.quality, []).append(channel_id)
            for quality, channels in sorted(qualities.items()):
                channels = sorted(channels)
                preview = ", ".join(channels[:4])
                suffix = f" and {len(channels) - 4} more" if len(channels) > 4 else ""
                meaning = (
                    "A missing channel can mean this source does not supply it; confirm data availability before treating it as a spacecraft fault."
                    if quality == "missing"
                    else "Review the data quality before interpreting these values."
                )
                warnings.append(
                    {
                        "key": f"warning:{run_id}:{frame.satellite_id}:quality:{quality}",
                        "satellite_id": frame.satellite_id,
                        "title": f"{len(channels)} {quality} telemetry readings",
                        "summary": f"Channels: {preview}{suffix}. {meaning}",
                        "fingerprint": canonical_hash({"quality": quality, "channels": channels}),
                    }
                )
            power = frame.channels.get("eps.unserved_power_w")
            if (
                power
                and power.quality == "valid"
                and isinstance(power.value, (int, float))
                and power.value > 0
            ):
                warnings.append(
                    {
                        "key": f"warning:{run_id}:{frame.satellite_id}:unserved-power",
                        "satellite_id": frame.satellite_id,
                        "title": "Unserved EPS power",
                        "summary": f"Committed eps.unserved_power_w is positive ({power.value:.2f} W).",
                        "fingerprint": "positive",
                    }
                )
            if frame.mode == "safe":
                warnings.append(
                    {
                        "key": f"warning:{run_id}:{frame.satellite_id}:safe-mode",
                        "satellite_id": frame.satellite_id,
                        "title": "Spacecraft reports safe mode",
                        "summary": "The current committed telemetry envelope explicitly reports mode: safe.",
                        "fingerprint": "safe",
                    }
                )
        return warnings

    def _latest_rows(self, connection: Connection, run_id: str) -> list[dict[str, Any]]:
        """Read one latest committed public frame per stream in a run."""
        stream_rows = connection.execute(
            select(tables.streams.c.stream_id, tables.streams.c.source_id).where(
                tables.streams.c.run_id == run_id
            )
        ).all()
        rows: list[dict[str, Any]] = []
        for stream_id, source_id in stream_rows:
            row = (
                connection.execute(
                    select(tables.frames.c.payload)
                    .where(
                        tables.frames.c.stream_id == stream_id,
                        tables.frames.c.source_id == source_id,
                        tables.frames.c.run_id == run_id,
                    )
                    .order_by(tables.frames.c.sequence.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if row is not None:
                rows.append(dict(row))
        return rows

    def _sync_warnings(self, connection: Connection, run_id: str) -> list[dict[str, Any]]:
        """Synchronize warning lifecycle state without treating each sample as new."""
        warnings = self._warnings(run_id, self._latest_rows(connection, run_id))
        mission = connection.execute(
            select(tables.mission_states.c.state).where(tables.mission_states.c.run_id == run_id)
        ).scalar_one_or_none()
        run = connection.execute(
            select(tables.runs.c.status, tables.runs.c.public_status).where(
                tables.runs.c.run_id == run_id
            )
        ).first()
        if (
            mission
            and mission.get("case_id")
            and mission.get("status") == "awaiting_decision"
            and run is not None
            and run.status == "paused"
            and run.public_status["committed_tick"] == mission["alert_at_s"]
        ):
            case = (
                connection.execute(
                    select(tables.operator_cases).where(
                        tables.operator_cases.c.case_id == mission["case_id"],
                        tables.operator_cases.c.run_id == run_id,
                        tables.operator_cases.c.user_id == mission["user_id"],
                    )
                )
                .mappings()
                .first()
            )
            if case and case["status"] == "open" and case["decision"] in {"pending", "revised"}:
                warnings.append(
                    {
                        "key": f"warning:{run_id}:{case['satellite_id']}:model:{mission['proposal_id']}",
                        "satellite_id": case["satellite_id"],
                        "title": case["title"],
                        "summary": f"Awaiting operator approval. {case['summary']}"[:4000],
                        "fingerprint": canonical_hash(
                            {
                                "proposal_id": mission["proposal_id"],
                                "recommendation": case["recommendation"],
                                "decision": case["decision"],
                            }
                        ),
                        "source": "model_prediction",
                        "severity": "critical",
                        "case_id": case["case_id"],
                    }
                )
        active = {item["key"]: item for item in warnings}
        existing = {
            row["notification_key"]: dict(row)
            for row in connection.execute(
                select(tables.operator_notification_state).where(
                    tables.operator_notification_state.c.run_id == run_id
                )
            ).mappings()
        }
        now = utc_now()
        for key, item in active.items():
            prior = existing.get(key)
            if prior is None:
                connection.execute(
                    insert(tables.operator_notification_state).values(
                        notification_key=key,
                        run_id=run_id,
                        satellite_id=item["satellite_id"],
                        kind="warning",
                        fingerprint=item["fingerprint"],
                        version=1,
                        active=True,
                        updated_at=now,
                    )
                )
                item["version"] = 1
            else:
                changed = not prior["active"] or prior["fingerprint"] != item["fingerprint"]
                version = prior["version"] + 1 if changed else prior["version"]
                if changed:
                    connection.execute(
                        update(tables.operator_notification_state)
                        .where(tables.operator_notification_state.c.notification_key == key)
                        .values(
                            satellite_id=item["satellite_id"],
                            fingerprint=item["fingerprint"],
                            version=version,
                            active=True,
                            updated_at=now,
                        )
                    )
                item["version"] = version
        for key, prior in existing.items():
            if prior["active"] and key not in active:
                connection.execute(
                    update(tables.operator_notification_state)
                    .where(tables.operator_notification_state.c.notification_key == key)
                    .values(active=False, updated_at=now)
                )
        return warnings

    def list_unread(self, run_id: str, user_id: str) -> dict[str, Any]:
        """Return unread visible warnings and open owned cases for a current run."""
        with self.database.writer_transaction() as connection:
            warnings = self._sync_warnings(connection, run_id)
            receipts = {
                row["notification_key"]: row["read_version"]
                for row in connection.execute(
                    select(tables.operator_notification_receipts).where(
                        tables.operator_notification_receipts.c.user_id == user_id
                    )
                ).mappings()
            }
            items = [
                {key: value for key, value in warning.items() if key != "fingerprint"}
                | {
                    "category": "warning",
                    "unread": receipts.get(warning["key"], 0) < warning["version"],
                }
                for warning in warnings
            ]
            for row in connection.execute(
                select(
                    tables.operator_cases.c.case_id,
                    tables.operator_cases.c.satellite_id,
                    tables.operator_cases.c.title,
                    tables.operator_cases.c.summary,
                    tables.operator_cases.c.revision,
                    tables.operator_cases.c.status,
                )
                .where(
                    tables.operator_cases.c.user_id == user_id,
                )
                .order_by(
                    tables.operator_cases.c.updated_at.desc(), tables.operator_cases.c.case_id
                )
                .limit(100)
            ).mappings():
                if row["status"] != "open":
                    continue
                key = f"case:{row['case_id']}"
                items.append(
                    {
                        "key": key,
                        "version": row["revision"],
                        "category": "case",
                        "satellite_id": row["satellite_id"],
                        "title": row["title"],
                        "summary": row["summary"][:4000] or "Operator case requires review.",
                        "unread": receipts.get(key, 0) < row["revision"],
                        "source": "operator_case",
                        "severity": "info",
                        "case_id": row["case_id"],
                    }
                )
            return {"items": items, "unread_count": sum(1 for item in items if item["unread"])}

    def mark_read(self, run_id: str, user_id: str, key: str, version: int) -> dict[str, Any]:
        """Persist acknowledgement only for a currently visible item and version."""
        listed = self.list_unread(run_id, user_id)
        with self.database.engine.connect() as connection:
            prior = connection.execute(
                select(tables.operator_notification_receipts.c.read_version).where(
                    tables.operator_notification_receipts.c.user_id == user_id,
                    tables.operator_notification_receipts.c.notification_key == key,
                )
            ).scalar_one_or_none()
        if prior is not None and prior >= version:
            return listed
        if not any(item["key"] == key and item["version"] == version for item in listed["items"]):
            raise ServiceError("notification_not_found", "Notification is no longer visible.", 404)
        with self.database.writer_transaction() as connection:
            existing = (
                connection.execute(
                    select(tables.operator_notification_receipts).where(
                        tables.operator_notification_receipts.c.user_id == user_id,
                        tables.operator_notification_receipts.c.notification_key == key,
                    )
                )
                .mappings()
                .first()
            )
            values = {"read_version": version, "read_at": utc_now()}
            if existing is None:
                connection.execute(
                    insert(tables.operator_notification_receipts).values(
                        user_id=user_id, notification_key=key, **values
                    )
                )
            elif existing["read_version"] < version:
                connection.execute(
                    update(tables.operator_notification_receipts)
                    .where(
                        tables.operator_notification_receipts.c.user_id == user_id,
                        tables.operator_notification_receipts.c.notification_key == key,
                    )
                    .values(**values)
                )
        return self.list_unread(run_id, user_id)
