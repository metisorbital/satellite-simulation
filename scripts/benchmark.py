"""Measure sustained paced throughput against an actual PostgreSQL database."""

import argparse
import ctypes
import json
import os
import platform
import subprocess
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import yaml
from fastapi.testclient import TestClient
from metis_sim.adapters import tables
from metis_sim.api.app import create_app
from metis_sim.logging import configure_logging
from metis_sim.settings import Settings
from sqlalchemy import Text, func, select

try:
    import resource
except ImportError:  # pragma: no cover - Windows does not provide resource.
    resource = None  # type: ignore[assignment]


REQUESTED_SPEED = 20
READ_CONTROL_P95_LIMIT_MS = 500.0
DEFAULT_SATELLITES = 10
DEFAULT_DURATION_S = 12_000
MAX_BATCH_WALL_S = 0.2
SCHEDULER_OVERHEAD_ALLOWANCE_S = 0.05
WALL_COMPLETION_ALLOWANCE_S = MAX_BATCH_WALL_S + SCHEDULER_OVERHEAD_ALLOWANCE_S


def _utc_now() -> str:
    """Return the current wall time as an RFC 3339 UTC timestamp.

    Returns
    -------
    str
        UTC timestamp with an explicit ``Z`` offset.
    """
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _command_output(command: list[str]) -> str | None:
    """Read a fixed local system command, returning ``None`` on failure.

    Parameters
    ----------
    command : list[str]
        Fixed command and arguments; benchmark input is never interpolated.

    Returns
    -------
    str or None
        Stripped standard output, or ``None`` when unavailable.
    """
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _physical_cpu_count() -> int | None:
    """Return host physical CPU cores where the local platform exposes them.

    Returns
    -------
    int or None
        Physical core count, or ``None`` when the host does not report it.
    """
    if sys.platform == "darwin":
        value = _command_output(["sysctl", "-n", "hw.physicalcpu"])
        return int(value) if value and value.isdigit() else None
    if sys.platform.startswith("linux"):
        pairs: set[tuple[str, str]] = set()
        physical_id: str | None = None
        core_id: str | None = None
        try:
            lines = Path("/proc/cpuinfo").read_text().splitlines()
        except OSError:
            return None
        for line in [*lines, ""]:
            if not line.strip():
                if physical_id is not None and core_id is not None:
                    pairs.add((physical_id, core_id))
                physical_id, core_id = None, None
                continue
            key, separator, value = line.partition(":")
            if separator and key.strip() == "physical id":
                physical_id = value.strip()
            elif separator and key.strip() == "core id":
                core_id = value.strip()
        return len(pairs) or None
    return None


def _memory_total_bytes() -> int | None:
    """Return host physical memory in bytes when the platform exposes it.

    Returns
    -------
    int or None
        Total physical memory in bytes, or ``None`` when unavailable.
    """
    if sys.platform == "darwin":
        value = _command_output(["sysctl", "-n", "hw.memsize"])
        return int(value) if value and value.isdigit() else None
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
        except (OSError, IndexError, ValueError):
            return None
    if sys.platform == "win32":  # pragma: no cover - Windows only.

        class MemoryStatus(ctypes.Structure):
            """Mirror the Windows ``MEMORYSTATUSEX`` structure."""

            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.ullTotalPhys)
    return None


def _hardware() -> dict[str, object]:
    """Collect physical hardware facts without adding runtime dependencies.

    Returns
    -------
    dict[str, object]
        Platform, CPU, and physical-memory fields. Optional values are ``None``
        when a host does not expose them.
    """
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_model": (
            _command_output(["sysctl", "-n", "machdep.cpu.brand_string"])
            if sys.platform == "darwin"
            else platform.processor() or None
        ),
        "logical_cpu_count": os.cpu_count(),
        "physical_cpu_count": _physical_cpu_count(),
        "physical_memory_bytes": _memory_total_bytes(),
    }


def _maximum_rss_bytes() -> tuple[int | None, str | None]:
    """Return maximum RSS for the benchmark process with platform-correct units.

    Returns
    -------
    tuple[int or None, str or None]
        Byte-normalized maximum RSS and the underlying unit source. Darwin's
        ``ru_maxrss`` is bytes; Linux and other Unix platforms report KiB.
    """
    if resource is None:
        return None, None
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if sys.platform == "darwin":
        return value, "resource.getrusage(RUSAGE_SELF).ru_maxrss_bytes"
    return value * 1024, "resource.getrusage(RUSAGE_SELF).ru_maxrss_kib"


def _p95(values: list[float]) -> float | None:
    """Return p95 milliseconds, preserving a missing measurement as ``None``.

    Parameters
    ----------
    values : list[float]
        Wall-latency samples in milliseconds.

    Returns
    -------
    float or None
        The 95th percentile or ``None`` if no request was measured.
    """
    return float(np.percentile(values, 95)) if values else None


def main() -> None:
    """Run a complete paced gate and save hardware, latency and integrity evidence."""
    configure_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--satellites", type=int, default=DEFAULT_SATELLITES)
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_S)
    parser.add_argument("--output", type=Path, default=Path("docs/validation/throughput.json"))
    args = parser.parse_args()
    if not 1 <= args.satellites <= DEFAULT_SATELLITES:
        parser.error("--satellites must be in [1, 10]")
    if args.duration < 1:
        parser.error("--duration must be positive")
    configuration = yaml.safe_load(Path("configs/demo.yaml").read_text())
    configuration["run"].update(duration_s=args.duration, speed=REQUESTED_SPEED)
    configuration["scenario"] = []
    template = configuration["satellites"][0]
    configuration["satellites"] = [
        {
            **template,
            "satellite_id": f"BENCH-{index:02d}",
            "name": f"Benchmark {index}",
            "operations": [],
            "orbit": {
                **template["orbit"],
                "true_anomaly_deg": float(index * 360 / args.satellites),
            },
        }
        for index in range(args.satellites)
    ]
    configuration["constellations"][0]["satellite_ids"] = [
        item["satellite_id"] for item in configuration["satellites"]
    ]
    settings = Settings(
        database_url=args.database_url,
        source_id="benchmark-" + uuid4().hex,
        session_secret=uuid4().hex + uuid4().hex,
        operator_token=uuid4().hex,
        consumer_token=uuid4().hex,
        evaluator_token=uuid4().hex,
    )
    app = create_app(settings, setup_schema=True, prepare_demo=False)
    benchmark_key = uuid4().hex
    read_latencies: list[float] = []
    control_latencies: list[float] = []
    benchmark_started_utc = _utc_now()
    safety_deadline_exceeded = False
    with TestClient(app) as client:
        headers = {
            "Authorization": "Bearer " + settings.operator_token,
            "Idempotency-Key": f"{benchmark_key}-configuration",
        }
        revision = client.post("/v1/configurations", json=configuration, headers=headers)
        revision.raise_for_status()
        prepare = time.monotonic()
        response = client.post(
            "/v1/runs",
            json={"configuration_id": revision.json()["configuration_id"]},
            headers={**headers, "Idempotency-Key": f"{benchmark_key}-run"},
        )
        response.raise_for_status()
        initialization_seconds = time.monotonic() - prepare
        run_id = response.json()["run_id"]
        visual_stop = threading.Event()
        visual_ready = threading.Event()
        visual_lock = threading.Lock()
        visual: dict[str, Any] = {
            "connected": False,
            "error_type": None,
            "message_count": 0,
            "message_types": {},
            "last_tick": None,
            "terminal_seen": False,
        }

        def receive_visual() -> None:
            """Receive one bounded ASGI visual stream until a terminal status.

            Notes
            -----
            The receiver uses the benchmark's authenticated operator capability.
            It exercises the server's bounded presentation projection, but not a
            browser renderer or a network transport.
            """
            try:
                with client.websocket_connect(
                    f"ws://testserver/v1/runs/{run_id}/visual",
                    headers={"Authorization": "Bearer " + settings.operator_token},
                ) as socket:
                    with visual_lock:
                        visual["connected"] = True
                    visual_ready.set()
                    while not visual_stop.is_set():
                        message = socket.receive_json()
                        status_message = message.get("status")
                        with visual_lock:
                            visual["message_count"] += 1
                            message_type = message.get("type", "unknown")
                            visual["message_types"][message_type] = (
                                visual["message_types"].get(message_type, 0) + 1
                            )
                            if status_message is not None:
                                visual["last_tick"] = status_message.get("committed_tick")
                                if status_message.get("status") in {
                                    "completed",
                                    "failed",
                                    "stopped",
                                    "aborted",
                                }:
                                    visual["terminal_seen"] = True
                                    break
            except (
                Exception
            ) as error:  # pragma: no cover - transport failures are environment dependent.
                with visual_lock:
                    visual["error_type"] = type(error).__name__
                visual_ready.set()

        visual_thread = threading.Thread(
            target=receive_visual, name="benchmark-visual", daemon=True
        )
        visual_thread.start()
        visual_ready.wait(timeout=5)
        control_at = time.monotonic()
        response = client.post(
            f"/v1/runs/{run_id}/control",
            json={"action": "start"},
            headers={**headers, "Idempotency-Key": f"{benchmark_key}-start"},
        )
        response.raise_for_status()
        control_latencies.append((time.monotonic() - control_at) * 1000)
        started = time.monotonic()
        paced_started_at = datetime.now(UTC)
        target_wall_duration = args.duration / REQUESTED_SPEED
        safety_deadline = started + target_wall_duration + WALL_COMPLETION_ALLOWANCE_S + 120
        last_control = started
        last_report = started
        status = response.json()
        while True:
            request_at = time.monotonic()
            snapshot = client.get(f"/v1/runs/{run_id}/snapshot", headers=headers)
            snapshot.raise_for_status()
            read_latencies.append((time.monotonic() - request_at) * 1000)
            status = snapshot.json()["status"]
            if status["status"] in {"completed", "failed", "stopped", "aborted"}:
                break
            now = time.monotonic()
            if now > safety_deadline:
                safety_deadline_exceeded = True
                control_at = time.monotonic()
                response = client.post(
                    f"/v1/runs/{run_id}/control",
                    json={"action": "stop"},
                    headers={**headers, "Idempotency-Key": str(uuid4())},
                )
                response.raise_for_status()
                control_latencies.append((time.monotonic() - control_at) * 1000)
                status = response.json()
                break
            if now - last_control >= 30:
                control_at = time.monotonic()
                response = client.post(
                    f"/v1/runs/{run_id}/control",
                    json={"action": "set_speed", "speed": REQUESTED_SPEED},
                    headers={**headers, "Idempotency-Key": str(uuid4())},
                )
                response.raise_for_status()
                control_latencies.append((time.monotonic() - control_at) * 1000)
                last_control = time.monotonic()
            if now - last_report >= 30:
                print(
                    json.dumps(
                        {
                            "elapsed_wall_s": round(now - started, 1),
                            "tick": status["committed_tick"],
                            "frames": status["frame_count"],
                        }
                    ),
                    flush=True,
                )
                last_report = now
            time.sleep(0.5)
        observed_wall_duration = time.monotonic() - started
        visual_terminal_deadline = time.monotonic() + 2
        while time.monotonic() < visual_terminal_deadline:
            with visual_lock:
                terminal_seen = bool(visual["terminal_seen"])
            if terminal_seen:
                break
            time.sleep(0.02)
        visual_stop.set()
        visual_thread.join(timeout=5)
        with visual_lock:
            visual_result = {**visual, "thread_stopped": not visual_thread.is_alive()}
        with app.state.database.engine.connect() as connection:
            bounds = connection.execute(
                select(
                    tables.frames.c.stream_id,
                    func.count(),
                    func.min(tables.frames.c.sequence),
                    func.max(tables.frames.c.sequence),
                )
                .where(tables.frames.c.run_id == run_id)
                .group_by(tables.frames.c.stream_id)
            ).all()
            payload_bytes = connection.execute(
                select(func.sum(func.octet_length(tables.frames.c.payload.cast(Text)))).where(
                    tables.frames.c.run_id == run_id
                )
            ).scalar_one()
            ended_at = connection.execute(
                select(tables.runs.c.ended_at).where(tables.runs.c.run_id == run_id)
            ).scalar_one()
        elapsed = (
            (ended_at - paced_started_at).total_seconds()
            if ended_at is not None
            else observed_wall_duration
        )
        frame_count = sum(row[1] for row in bounds)
        stream_count = len(bounds)
        expected_frames = (args.duration + 1) * args.satellites
        allowed_wall_duration = target_wall_duration + WALL_COMPLETION_ALLOWANCE_S
        minimum_effective_speed = args.duration / allowed_wall_duration
        minimum_sustained_frames_per_s = args.duration * args.satellites / allowed_wall_duration
        maximum_rss_bytes, maximum_rss_source = _maximum_rss_bytes()
        result: dict[str, Any] = {
            "run_id": run_id,
            "benchmark_started_utc": benchmark_started_utc,
            "benchmark_ended_utc": _utc_now(),
            "hardware": _hardware(),
            "maximum_rss_bytes": maximum_rss_bytes,
            "maximum_rss_source": maximum_rss_source,
            "database": "PostgreSQL via SQLAlchemy/Psycopg",
            "satellites": args.satellites,
            "simulated_duration_s": args.duration,
            "requested_speed": REQUESTED_SPEED,
            "paced_started_utc": paced_started_at.isoformat().replace("+00:00", "Z"),
            "run_ended_utc": ended_at.isoformat().replace("+00:00", "Z") if ended_at else None,
            "target_wall_duration_s": target_wall_duration,
            "wall_completion_allowance_s": WALL_COMPLETION_ALLOWANCE_S,
            "allowed_wall_duration_s": allowed_wall_duration,
            "target_sustained_frames_per_s": args.satellites * REQUESTED_SPEED,
            "minimum_effective_speed_with_allowance": minimum_effective_speed,
            "minimum_sustained_frames_per_s_with_allowance": minimum_sustained_frames_per_s,
            "wall_duration_s": elapsed,
            "observed_wall_duration_s": observed_wall_duration,
            "effective_speed": args.duration / elapsed,
            "sustained_frames_per_s": (frame_count - stream_count) / elapsed if elapsed else 0.0,
            "initialization_wall_s": initialization_seconds,
            "frame_count": frame_count,
            "expected_frames": expected_frames,
            "stream_count": stream_count,
            "expected_stream_count": args.satellites,
            "zero_sequence_gaps": stream_count == args.satellites
            and all(
                row[1] == args.duration + 1 and row[2] == 0 and row[3] == args.duration
                for row in bounds
            ),
            "read_p95_ms": _p95(read_latencies),
            "read_max_ms": max(read_latencies) if read_latencies else None,
            "control_p95_ms": _p95(control_latencies),
            "control_max_ms": max(control_latencies) if control_latencies else None,
            "read_requests": len(read_latencies),
            "control_requests": len(control_latencies),
            "mean_payload_bytes_per_frame": payload_bytes / frame_count if frame_count else None,
            "storage": app.state.database.storage_stats(),
            "run_status": status["status"],
            "visual_consumer": visual_result,
            "safety_deadline_exceeded": safety_deadline_exceeded,
            "source_sha256": app.state.repository.private_run(run_id)["manifest"]["source_sha256"],
            "notes": "Real wall-clock paced runner and PostgreSQL; ASGI in-process HTTP adapter. Browser FPS and network transport are measured separately. Preparation is excluded from paced throughput. The default is the specification workload: ten satellites at 20x for 600 wall seconds. The 0.25-second completion allowance is the runner's 0.2-second maximum batch plus one 0.05-second scheduler interval; exact requested targets remain reported.",
        }
        gates = {
            "completed": result["run_status"] == "completed",
            "within_target_wall_duration_with_allowance": result["wall_duration_s"]
            <= result["allowed_wall_duration_s"],
            "effective_speed_within_completion_allowance": result["effective_speed"]
            >= result["minimum_effective_speed_with_allowance"],
            "sustained_frames_per_s_within_completion_allowance": result["sustained_frames_per_s"]
            >= result["minimum_sustained_frames_per_s_with_allowance"],
            "stream_count_matches_satellites": result["stream_count"] == result["satellites"],
            "every_stream_has_complete_contiguous_sequence": result["zero_sequence_gaps"],
            "frame_count_matches_expected": result["frame_count"] == result["expected_frames"],
            "read_p95_below_500_ms": result["read_p95_ms"] is not None
            and result["read_p95_ms"] < READ_CONTROL_P95_LIMIT_MS,
            "control_p95_below_500_ms": result["control_p95_ms"] is not None
            and result["control_p95_ms"] < READ_CONTROL_P95_LIMIT_MS,
            "visual_consumer_connected": result["visual_consumer"]["connected"],
            "visual_consumer_reached_terminal_tick": (
                result["visual_consumer"]["terminal_seen"]
                and result["visual_consumer"]["last_tick"] == status["committed_tick"]
                and result["visual_consumer"]["thread_stopped"]
            ),
            "safety_deadline_not_exceeded": not result["safety_deadline_exceeded"],
        }
        result["gates"] = gates
        result["passed"] = all(gates.values())
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)
        if not result["passed"]:
            raise SystemExit("Capacity or integrity gate failed")


if __name__ == "__main__":
    main()
