"""Composition of validated configuration, physical engines and durable runs."""

import hashlib
import json
import logging
import platform
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from metis_sim.adapters.configuration import (
    configuration_hash,
    load_configuration,
    normalize_configuration,
)
from metis_sim.adapters.records import canonical_hash, utc_now
from metis_sim.adapters.repository import Idempotent, Repository
from metis_sim.application.errors import ServiceError
from metis_sim.application.measurement import MeasurementProjector
from metis_sim.application.runner import PreparedRun, Runner
from metis_sim.domain.config import SimulationConfig
from metis_sim.domain.public import (
    OrbitPoint,
    PublicModelProvenance,
    PublicRunStatus,
    PublicSpacecraft,
    SatelliteTrajectory,
    Trajectory,
)
from metis_sim.models.engine import SimulationEngine

logger = logging.getLogger(__name__)


class SimulationService:
    """Own application mutation ordering and prepared-engine lifetimes.

    Parameters
    ----------
    repository : Repository
        Private transactional port.
    runner : Runner
        Single authoritative writer thread.
    """

    def __init__(self, repository: Repository, runner: Runner) -> None:
        self.repository, self.runner = repository, runner
        self.mutations = threading.RLock()
        self.demo_run_id: str | None = None

    def create_configuration(self, config: SimulationConfig, token: Idempotent) -> dict[str, Any]:
        """Persist one fully resolved immutable configuration revision."""
        with self.mutations:
            return self.repository.save_configuration(
                config.model_dump(mode="json"),
                normalize_configuration(config),
                configuration_hash(config),
                token,
            )

    def create_run(self, configuration_id: str, retain: bool, token: Idempotent) -> dict[str, Any]:
        """Validate ephemeris coverage and prepare an independent reproducible execution."""
        with self.mutations:
            existing = self.repository.existing(token)
            if existing is not None:
                return existing
            revision = self.repository.configuration(configuration_id)
            config = load_configuration(json.dumps(revision["configuration"]), "json")
            # Bound retained CPU caches. Durable history remains replayable after eviction.
            if len(self.runner.prepared) >= 3:
                candidates = [
                    run_id
                    for run_id in self.runner.prepared
                    if run_id != self.runner.active_id
                    and self.repository.status(run_id)["status"]
                    in {"completed", "stopped", "failed", "aborted"}
                ]
                if not candidates:
                    raise ServiceError(
                        "prepared_run_limit",
                        "At most three prepared runs may be held; stop an unused run.",
                    )
                del self.runner.prepared[candidates[0]]
            engine = SimulationEngine(config).initialize()
            run_id = str(uuid4())
            spacecraft = []
            for satellite in sorted(config.satellites, key=lambda item: item.satellite_id):
                profile = config.profiles[satellite.profile_id]
                spacecraft.append(
                    PublicSpacecraft.model_validate(
                        dict(
                            satellite_id=satellite.satellite_id,
                            name=satellite.name,
                            color=satellite.visual.color,
                            stream_id=str(uuid4()),
                            capacity_wh=profile.battery.usable_capacity_wh,
                            panel_area_m2=profile.panel.area_m2,
                            public_limits=[limit.model_dump() for limit in profile.public_limits],
                        )
                    )
                )
            status = PublicRunStatus.model_validate(
                dict(
                    run_id=run_id,
                    status="created",
                    epoch_utc=config.run.epoch_utc,
                    duration_s=config.run.duration_s,
                    requested_speed=config.run.speed,
                    satellites=spacecraft,
                    model_provenance={
                        key: engine.provenance[key]
                        for key in PublicModelProvenance.__annotations__
                        if key in engine.provenance
                    },
                )
            )
            manifest = dict(
                manifest_version="manifest.v1",
                run_id=run_id,
                source_kind="synthetic",
                configuration=revision["configuration"],
                resolved_configuration=revision["resolved"],
                configuration_hash=revision["canonical_hash"],
                root_seed=config.run.seed,
                canonicalization="RFC8785",
                model_provenance=engine.provenance,
                python_version=platform.python_version(),
                created_at=utc_now().isoformat(),
                dependency_lock_sha256=self._file_hash(Path("uv.lock")),
                source_sha256=self._source_hash(),
                random_generator="numpy.PCG64DXSM",
                seed_derivation="SHA256(root_seed,satellite_id,sensor_channel_id); noise disabled in P0",
            )
            result = self.repository.create_run(
                configuration_id, status.model_dump(mode="json"), manifest, retain, token
            )
            self.runner.prepared[run_id] = PreparedRun(
                config,
                engine,
                MeasurementProjector(
                    config,
                    self.repository.database.source_id,
                    {s.satellite_id: s.stream_id for s in spacecraft},
                ),
            )
            return result

    def trajectory(self, run_id: str, start: int, end: int, step: int) -> Trajectory:
        """Return backend orbit samples only, never precomputed future EPS state."""
        status = self.repository.status(run_id)
        if (
            not 0 <= start <= end <= status["duration_s"]
            or step < 1
            or end - start > 3600
            or (end - start) // step + 1 > 3601
        ):
            raise ServiceError(
                "invalid_trajectory",
                "Trajectory must be within the run and at most one hour / 3601 points per satellite.",
                422,
            )
        prepared = self.runner.prepared.get(run_id)
        if prepared is None:
            raise ServiceError(
                "trajectory_not_prepared",
                "Orbit preview is unavailable after this run's engine was released; retained telemetry remains available.",
                409,
            )
        satellites = []
        for satellite in status["satellites"]:
            samples = prepared.engine.trajectory(satellite["satellite_id"], start, end, step)
            satellites.append(
                SatelliteTrajectory(
                    satellite_id=satellite["satellite_id"],
                    samples=[
                        OrbitPoint(
                            elapsed_s=s.tick,
                            observed_at=s.observed_at,
                            position_itrs_m=s.position_itrf_m,
                            velocity_itrs_m_s=s.velocity_itrf_m_s,
                        )
                        for s in samples
                    ],
                )
            )
        return Trajectory(run_id=run_id, satellites=satellites)

    def prepare_demo(self, path: Path, at_tick: int = 0) -> str:
        """Create a local run, optionally persisting genuine history to a paused demo point."""
        config = load_configuration(path.read_text())
        unique = str(uuid4())
        revision = self.create_configuration(
            config, ("local:configuration", unique, canonical_hash(config.model_dump(mode="json")))
        )
        status = self.create_run(
            revision["configuration_id"], False, ("local:run", unique, canonical_hash(revision))
        )
        self.demo_run_id = status["run_id"]
        logger.info("demo_preparation_started", extra={"run_id": self.demo_run_id, "tick": at_tick})
        if at_tick <= 0:
            logger.info(
                "demo_prepared",
                extra={
                    "run_id": self.demo_run_id,
                    "tick": 0,
                    "status": "created",
                    "frame_count": 0,
                },
            )
            return self.demo_run_id
        if at_tick >= config.run.duration_s:
            raise ValueError("Demo starting tick must be less than the configured duration")
        prepared = self.runner.prepared[self.demo_run_id]
        status["status"] = "running"
        self.repository.commit(status, [], [], [])
        for first in range(0, at_tick + 1, 4):
            frames, events, truth = [], [], []
            final = min(first + 3, at_tick)
            for tick in range(first, final + 1):
                f, e, t = prepared.projector.project(prepared.engine.sample(tick))
                frames.extend(f)
                events.extend(e)
                truth.extend(t)
            status.update(
                committed_tick=final,
                committed_at=frames[-1]["observed_at"],
                frame_count=(final + 1) * len(status["satellites"]),
            )
            self.repository.commit(status, frames, events, truth)
            if final % 1000 < 4 or final == at_tick:
                logger.info(
                    "demo_preparation_progress",
                    extra={
                        "run_id": self.demo_run_id,
                        "tick": final,
                        "frame_count": status["frame_count"],
                    },
                )
        status["status"] = "paused"
        self.repository.commit(status, [], [], [])
        self.runner.active_id = self.demo_run_id
        logger.info(
            "demo_prepared",
            extra={
                "run_id": self.demo_run_id,
                "tick": status["committed_tick"],
                "status": status["status"],
                "frame_count": status["frame_count"],
            },
        )
        return self.demo_run_id

    @staticmethod
    def _file_hash(path: Path) -> str | None:
        return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

    @staticmethod
    def _source_hash() -> str:
        digest = hashlib.sha256()
        root = Path(__file__).resolve().parents[1]
        for path in sorted(root.rglob("*.py")):
            digest.update(str(path.relative_to(root)).encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()
