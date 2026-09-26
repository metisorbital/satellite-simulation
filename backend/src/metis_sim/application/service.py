"""Composition of validated configuration, physical engines and durable runs."""

import hashlib
import json
import logging
import platform
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast
from uuid import uuid4

from metis_sim.adapters.configuration import (
    configuration_hash,
    load_configuration,
    normalize_configuration,
)
from metis_sim.adapters.observed import ObservedRepository
from metis_sim.adapters.records import canonical_hash, utc_now
from metis_sim.adapters.repository import TERMINAL, Idempotent, Repository
from metis_sim.application.configured_orbit import configured_orbit_points, default_bupt1_orbit
from metis_sim.application.errors import ServiceError
from metis_sim.application.measurement import MeasurementProjector
from metis_sim.application.replay import PreparedReplay
from metis_sim.application.runner import PreparedRun, Runner
from metis_sim.domain.config import OrbitConfiguration, SimulationConfig
from metis_sim.domain.configured_orbit import ConfiguredOrbit
from metis_sim.domain.observed import ObservedDataset, ObservedSample
from metis_sim.domain.public import (
    OrbitPoint,
    PublicDataset,
    PublicModelProvenance,
    PublicRunStatus,
    PublicSpacecraft,
    SatelliteTrajectory,
    Trajectory,
)
from metis_sim.models.engine import SimulationEngine
from metis_sim.models.frames import EarthOrientationError

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
        self.viewer_runs: set[str] = set()
        self.observed = ObservedRepository(repository.database)

    def create_configuration(self, config: SimulationConfig, token: Idempotent) -> dict[str, Any]:
        """Persist one fully resolved immutable configuration revision.

        Parameters
        ----------
        config : SimulationConfig
            Validated input whose normalized form and hash become immutable.
        token : Idempotent
            Scope, idempotency key, and canonical request hash for retries.

        Returns
        -------
        dict[str, Any]
            Revision identity, canonical hash, and schema version.
        """
        with self.mutations:
            return self.repository.save_configuration(
                config.model_dump(mode="json"),
                normalize_configuration(config),
                configuration_hash(config),
                token,
            )

    def editable_satellites(self, run_id: str) -> list[dict[str, Any]]:
        """Return only satellite inputs that a viewer may safely edit.

        Parameters
        ----------
        run_id : str
            Run authorized by the viewer session.

        Returns
        -------
        list of dict
            Public satellite definitions without private scenario or profile data.
        """
        status = self.repository.status(run_id)
        if status.get("source_kind") == "observed":
            display = self._configured_orbit(run_id, status)
            satellite = status["satellites"][0]
            return [
                {
                    "satellite_id": satellite["satellite_id"],
                    "name": satellite["name"],
                    "visual": {"color": satellite["color"]},
                    "orbit": display.orbit.model_dump(mode="json"),
                    "orbit_provenance": display.model_dump(mode="json", exclude={"orbit"}),
                }
            ]
        config = self._run_config(run_id)
        result = []
        for sat in config.satellites:
            profile = config.profiles[sat.profile_id]
            result.append(
                {
                    **sat.model_dump(mode="json"),
                    "power": {
                        "panel_area_m2": profile.panel.area_m2,
                        "panel_efficiency": profile.panel.efficiency,
                        "battery_capacity_wh": profile.battery.usable_capacity_wh,
                        "battery_initial_soc": profile.battery.initial_soc,
                        "loads_w": dict(profile.loads_w),
                    },
                }
            )
        return result

    def recreate_viewer_run(
        self,
        run_id: str,
        satellites: list[dict[str, Any]] | None,
        token: Idempotent,
        *,
        viewer_expires_at: float | None = None,
        data_source: Literal["physics", "satellitecots"] | None = None,
        dataset_id: str | None = None,
        start_elapsed_s: int = 0,
    ) -> dict[str, Any]:
        """Create a fresh immutable revision and run for a viewer edit or reset.

        Parameters
        ----------
        run_id : str
            Source run authorized by the viewer session.
        satellites : list of dict or None
            Replacement constellation, or ``None`` to reset the current input.
        token : Idempotent
            Request identity shared by revision and run creation.
        viewer_expires_at : float or None
            Expiry of the replacement mock operator session and its private lease.
        data_source : str or None
            Explicit source selection, or retain the current run's source on reset.
        dataset_id : str or None
            Imported archive identity; retained when resetting an observed run.
        start_elapsed_s : int, default=0
            Source-time position for a recorded playback.

        Returns
        -------
        dict[str, Any]
            New public run status with independent stream identities.
        """
        with self.mutations:
            existing = self.repository.existing((token[0] + ":run", token[1], token[2]))
            if existing is not None:
                return existing
            source = self.repository.status(run_id)
            if source["status"] in {"running", "paused"}:
                raise ServiceError(
                    "run_active", "Stop the current run before editing or resetting.", 409
                )
            selected_source = data_source or source.get("data_source", "physics")
            display_orbit = (
                self._configured_orbit(run_id, source)
                if selected_source == "satellitecots" and source.get("source_kind") == "observed"
                else None
            )
            if selected_source == "satellitecots" and satellites is not None:
                expected = self.editable_satellites(run_id)
                if len(satellites) != 1 or len(expected) != 1 or display_orbit is None:
                    raise ServiceError(
                        "observed_configuration_fixed",
                        "Recorded spacecraft membership is fixed; edit only its configured orbit.",
                        422,
                    )
                submitted = dict(satellites[0])
                supplied_orbit = submitted.pop("orbit", None)
                baseline = dict(expected[0])
                baseline.pop("orbit")
                if submitted != baseline:
                    raise ServiceError(
                        "observed_configuration_fixed",
                        "Only configured orbit fields can change for recorded spacecraft.",
                        422,
                    )
                updated_orbit = OrbitConfiguration.model_validate(supplied_orbit)
                default = default_bupt1_orbit(display_orbit.epoch_utc)
                display_orbit = display_orbit.model_copy(
                    update={
                        "orbit": updated_orbit,
                        "operator_modified": updated_orbit != default.orbit,
                    }
                )
                satellites = None
            if selected_source == "satellitecots" and dataset_id is None:
                dataset_id = source.get("dataset_id")
            if selected_source == "satellitecots":
                self._replay_start(dataset_id, start_elapsed_s)
            elif dataset_id is not None or start_elapsed_s:
                raise ServiceError(
                    "invalid_source", "Physics runs do not accept an archive position.", 422
                )
            config = self._run_config(run_id)
            if satellites is not None:
                if not 1 <= len(satellites) <= 10:
                    raise ServiceError(
                        "invalid_constellation", "Use between 1 and 10 satellites.", 422
                    )
                ids = [sat.get("satellite_id") for sat in satellites]
                if any(not isinstance(item, str) or not item for item in ids):
                    raise ServiceError(
                        "invalid_constellation", "Satellite IDs must be strings.", 422
                    )
                if len(ids) != len(set(ids)):
                    raise ServiceError(
                        "invalid_constellation", "Satellite IDs must be unique.", 422
                    )
                # Remove hidden scenario inputs when editing their spacecraft.
                updated = config.model_dump(mode="json")
                updated["satellites"] = []
                expected_power = {
                    "panel_area_m2",
                    "panel_efficiency",
                    "battery_capacity_wh",
                    "battery_initial_soc",
                    "loads_w",
                }
                for satellite in satellites:
                    definition = dict(satellite)
                    power = definition.pop("power", None)
                    if power is not None:
                        if not isinstance(power, dict) or set(power) != expected_power:
                            raise ServiceError(
                                "invalid_power", "Power parameters are incomplete.", 422
                            )
                        profile_id = definition.get("profile_id")
                        if profile_id not in updated["profiles"]:
                            raise ServiceError(
                                "invalid_profile", "Unknown spacecraft profile.", 422
                            )
                        unique_profile_id = (
                            "v_"
                            + hashlib.sha256(
                                definition["satellite_id"].encode("utf-8")
                            ).hexdigest()[:32]
                        )
                        profile = json.loads(json.dumps(updated["profiles"][profile_id]))
                        profile["panel"]["area_m2"] = power["panel_area_m2"]
                        profile["panel"]["efficiency"] = power["panel_efficiency"]
                        profile["battery"]["usable_capacity_wh"] = power["battery_capacity_wh"]
                        profile["battery"]["initial_soc"] = power["battery_initial_soc"]
                        profile["loads_w"] = power["loads_w"]
                        updated["profiles"][unique_profile_id] = profile
                        definition["profile_id"] = unique_profile_id
                    updated["satellites"].append(definition)
                updated["constellations"] = [
                    {**constellation, "satellite_ids": ids}
                    for constellation in updated["constellations"]
                ]
                updated["scenario"] = []
                config = load_configuration(json.dumps(updated), "json")
            # Revalidate copied cross-object references and profile selections.
            config = load_configuration(json.dumps(config.model_dump(mode="json")), "json")
            revision = self.create_configuration(
                config, (token[0] + ":configuration", token[1], token[2])
            )
            # An abandoned created run can be replaced without consuming a
            # fourth prepared slot; restore it if preparation fails.
            released = None
            if source["status"] == "created" and len(self.runner.prepared) >= 3:
                released = self.runner.prepared.pop(run_id, None)
            try:
                result = self.create_run(
                    revision["configuration_id"],
                    False,
                    (token[0] + ":run", token[1], token[2]),
                    viewer=True,
                    user_id=self.repository.private_run(run_id)["user_id"],
                    viewer_expires_at=viewer_expires_at,
                    data_source=selected_source,
                    dataset_id=dataset_id,
                    start_elapsed_s=start_elapsed_s,
                    display_orbit=display_orbit,
                )
            except Exception:
                if released is not None:
                    self.runner.prepared[run_id] = released
                raise
            if source["status"] == "created" or source["status"] in TERMINAL:
                self.runner.prepared.pop(run_id, None)
                self.viewer_runs.discard(run_id)
            return result

    def _run_config(self, run_id: str) -> SimulationConfig:
        """Load the immutable configuration belonging to a run for internal use."""
        run = self.repository.private_run(run_id)
        revision = self.repository.configuration(run["configuration_id"])
        return load_configuration(json.dumps(revision["configuration"]), "json")

    def _configured_orbit(self, run_id: str, status: dict[str, Any]) -> ConfiguredOrbit:
        manifest = self.repository.private_run(run_id)["manifest"]
        if "display_orbit" in manifest:
            return ConfiguredOrbit.model_validate_json(json.dumps(manifest["display_orbit"]))
        # Existing observed runs retain their original data. A later edit/reset
        # snapshots these sourced defaults without altering that historical run.
        return default_bupt1_orbit(
            datetime.fromisoformat(status["epoch_utc"].replace("Z", "+00:00"))
        )

    def ensure_prepared_viewer_run(self, run_id: str) -> None:
        """Restore an idle browser run's physical engine after slot eviction.

        Parameters
        ----------
        run_id : str
            Created run authorized by an interactive viewer cookie.

        Raises
        ------
        ServiceError
            If the run is no longer creatable or capacity is unavailable.
        """
        with self.mutations:
            if run_id in self.runner.prepared:
                return
            status = self.repository.status(run_id)
            if status["status"] != "created":
                return
            if len(self.runner.prepared) >= 3:
                candidates = [
                    candidate
                    for candidate in self.runner.prepared
                    if candidate in self.viewer_runs
                    and candidate != self.runner.active_id
                    and self.repository.status(candidate)["status"] == "created"
                ]
                if not candidates:
                    raise ServiceError(
                        "prepared_run_limit", "The simulator is busy; retry shortly.", 409
                    )
                evicted_id = candidates[0]
                del self.runner.prepared[evicted_id]
                self.viewer_runs.discard(evicted_id)
            if status.get("data_source") == "satellitecots":
                manifest = self.repository.private_run(run_id)["manifest"]
                dataset = self.observed.get_dataset(manifest["dataset_id"])
                if dataset is None:
                    raise ServiceError("dataset_not_found", "Imported archive is unavailable.", 404)
                self.runner.prepared[run_id] = PreparedReplay(
                    self.observed,
                    dataset,
                    self.repository.database.source_id,
                    status["satellites"][0]["stream_id"],
                    manifest["replay_start_sequence"],
                )
                self.viewer_runs.add(run_id)
                return
            config = self._run_config(run_id)
            engine = SimulationEngine(config).initialize()
            self.runner.prepared[run_id] = PreparedRun(
                config,
                engine,
                MeasurementProjector(
                    config,
                    self.repository.database.source_id,
                    {sat["satellite_id"]: sat["stream_id"] for sat in status["satellites"]},
                ),
            )
            self.viewer_runs.add(run_id)

    def create_run(
        self,
        configuration_id: str,
        retain: bool,
        token: Idempotent,
        *,
        viewer: bool = False,
        user_id: str | None = None,
        viewer_expires_at: float | None = None,
        data_source: Literal["physics", "satellitecots"] = "physics",
        dataset_id: str | None = None,
        start_elapsed_s: int = 0,
        display_orbit: ConfiguredOrbit | None = None,
    ) -> dict[str, Any]:
        """Prepare an independent run from a saved configuration revision.

        Parameters
        ----------
        configuration_id : str
            Immutable revision to execute.
        retain : bool
            Whether durable run history remains after normal expiry cleanup.
        token : Idempotent
            Scope, idempotency key, and canonical request hash for retries.
        viewer : bool, default=False
            Whether the new run is browser-owned and may later be evicted while idle.
        user_id : str or None
            Stable demo operator UUID persisted only in the private run record.
        viewer_expires_at : float or None
            Absolute expiry of a mock-owned run's browser session.
        data_source : str, default='physics'
            Authoritative producer: numerical simulation or recorded observations.
        dataset_id : str or None
            Imported recorded source; optional when exactly one archive is installed.
        start_elapsed_s : int, default=0
            Desired recorded position, snapped to the next actual observation.
        display_orbit : ConfiguredOrbit or None
            Existing sourced orbit snapshot to preserve across recorded resets
            and seeks. This never supplies observed telemetry channels.

        Returns
        -------
        dict[str, Any]
            Created public run status with newly allocated stream identities.

        Notes
        -----
        Preparation checks pinned time data and computes the physical run before
        it is made available to the writer. This work runs outside the HTTP
        event loop.
        """
        if data_source == "satellitecots":
            return self._create_replay_run(
                configuration_id,
                retain,
                token,
                viewer=viewer,
                user_id=user_id,
                viewer_expires_at=viewer_expires_at,
                dataset_id=dataset_id,
                start_elapsed_s=start_elapsed_s,
                display_orbit=display_orbit,
            )
        if dataset_id is not None or start_elapsed_s:
            raise ServiceError(
                "invalid_source", "Physics runs do not accept an archive position.", 422
            )
        with self.mutations:
            existing = self.repository.existing(token)
            if existing is not None:
                return existing
            revision = self.repository.configuration(configuration_id)
            config = load_configuration(json.dumps(revision["configuration"]), "json")
            self._make_prepared_room()
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
                viewer_owned=viewer,
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
            if user_id is not None:
                if viewer_expires_at is None:
                    raise ValueError("Mock operator runs require a durable session expiry")
                manifest["viewer_expires_at"] = viewer_expires_at
            result = self.repository.create_run(
                configuration_id,
                status.model_dump(mode="json"),
                manifest,
                retain,
                token,
                catalog_versions={
                    satellite.satellite_id: config.profiles[satellite.profile_id].sensors.catalog
                    for satellite in config.satellites
                },
                user_id=user_id,
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
            if viewer:
                self.viewer_runs.add(run_id)
            return result

    def datasets(self) -> list[PublicDataset]:
        """List installed source metadata without disclosing upcoming telemetry.

        Returns
        -------
        list of PublicDataset
            Available immutable archives, projected through an explicit allowlist.
        """
        return [
            PublicDataset(
                dataset_id=dataset.dataset_id,
                title=dataset.title,
                satellite_id=dataset.satellite_id,
                catalog_version=dataset.catalog_version,
                observed_start=dataset.observed_start,
                observed_end=dataset.observed_end,
                duration_s=dataset.duration_s,
                sample_count=dataset.sample_count,
            )
            for dataset in self.observed.list_datasets()
        ]

    def seek_viewer_run(
        self,
        run_id: str,
        elapsed_s: int,
        token: Idempotent,
        *,
        viewer_expires_at: float | None = None,
    ) -> dict[str, Any]:
        """Stop a recorded playback and prepare a fresh stream at a source time.

        Parameters
        ----------
        run_id : str
            Current viewer-authorized observed run.
        elapsed_s : int
            Requested offset from the immutable archive's original epoch.
        token : Idempotent
            Durable identity reused by the stop and replacement-run operations.
        viewer_expires_at : float or None
            Lease expiry for the replacement mock operator session.

        Returns
        -------
        dict
            Created run at the nearest existing sample at or after the request.
            The viewer explicitly starts playback after reviewing the selection.
        """
        with self.mutations:
            existing = self.repository.existing((token[0] + ":run", token[1], token[2]))
            if existing is not None:
                return existing
            status = self.repository.status(run_id)
            if status.get("data_source") != "satellitecots":
                raise ServiceError(
                    "seek_requires_observed", "Select a recorded source to seek.", 422
                )
            # Validate and resolve before stopping an active run.
            self._replay_start(status["dataset_id"], elapsed_s)
            if status["status"] in {"running", "paused"}:
                self.runner.command(
                    run_id,
                    "stop",
                    None,
                    (token[0] + ":stop", token[1], token[2]),
                    user_id=self.repository.private_run(run_id)["user_id"],
                )
            return self.recreate_viewer_run(
                run_id,
                None,
                token,
                viewer_expires_at=viewer_expires_at,
                start_elapsed_s=elapsed_s,
            )

    def _replay_start(
        self, dataset_id: str | None, elapsed_s: int
    ) -> tuple[ObservedDataset, ObservedSample]:
        if dataset_id is None:
            available = self.observed.list_datasets()
            if len(available) != 1:
                raise ServiceError(
                    "dataset_selection_required" if available else "dataset_not_found",
                    "Choose an installed recorded archive."
                    if available
                    else "No recorded archive is installed.",
                    422 if available else 404,
                )
            dataset = available[0]
        else:
            selected = self.observed.get_dataset(dataset_id)
            if selected is None:
                raise ServiceError("dataset_not_found", "Imported archive is unavailable.", 404)
            dataset = selected
        if type(elapsed_s) is not int or not 0 <= elapsed_s <= dataset.duration_s:
            raise ServiceError("invalid_seek", "Playback position must be within the archive.", 422)
        sample = self.observed.sample_at_or_after(dataset.dataset_id, elapsed_s)
        if sample is None:
            raise ServiceError(
                "dataset_incomplete", "The archive has no sample at this position.", 409
            )
        return dataset, sample

    def _create_replay_run(
        self,
        configuration_id: str,
        retain: bool,
        token: Idempotent,
        *,
        viewer: bool,
        user_id: str | None,
        viewer_expires_at: float | None,
        dataset_id: str | None,
        start_elapsed_s: int,
        display_orbit: ConfiguredOrbit | None,
    ) -> dict[str, Any]:
        with self.mutations:
            existing = self.repository.existing(token)
            if existing is not None:
                return existing
            # This immutable revision is retained only for switching back to
            # physics; no synthetic configuration is used to produce observations.
            revision = self.repository.configuration(configuration_id)
            config = load_configuration(json.dumps(revision["configuration"]), "json")
            dataset, first = self._replay_start(dataset_id, start_elapsed_s)
            display_orbit = display_orbit or default_bupt1_orbit(dataset.observed_start)
            self._make_prepared_room()
            run_id, stream_id = str(uuid4()), str(uuid4())
            provenance = {
                key: value
                for key, value in dataset.provenance.items()
                if key in PublicModelProvenance.__annotations__
            }
            status = PublicRunStatus(
                run_id=run_id,
                status="created",
                epoch_utc=dataset.observed_start,
                duration_s=dataset.duration_s,
                playback_start_s=first.elapsed_s,
                requested_speed=config.run.speed,
                committed_sequence=-1,
                satellites=[
                    PublicSpacecraft(
                        satellite_id=dataset.satellite_id,
                        name=dataset.satellite_id,
                        color="#a78bfa",
                        stream_id=stream_id,
                        capacity_wh=None,
                        panel_area_m2=None,
                    )
                ],
                source_kind="observed",
                data_source="satellitecots",
                dataset_id=dataset.dataset_id,
                dataset_title=dataset.title,
                time_domain="mission_utc",
                nominal_cadence_s=1.0,
                model_provenance=cast(PublicModelProvenance, provenance),
            )
            manifest = dict(
                manifest_version="observed-replay.v1",
                run_id=run_id,
                source_kind="observed",
                viewer_owned=viewer,
                dataset_id=dataset.dataset_id,
                dataset_provenance=dataset.provenance,
                replay_start_sequence=first.sequence,
                playback_start_s=first.elapsed_s,
                created_at=utc_now().isoformat(),
                python_version=platform.python_version(),
                source_sha256=self._source_hash(),
                display_orbit=display_orbit.model_dump(mode="json"),
            )
            if user_id is not None:
                if viewer_expires_at is None:
                    raise ValueError("Mock operator runs require a durable session expiry")
                manifest["viewer_expires_at"] = viewer_expires_at
            result = self.repository.create_run(
                configuration_id,
                status.model_dump(mode="json"),
                manifest,
                retain,
                token,
                catalog_versions={dataset.satellite_id: dataset.catalog_version},
                user_id=user_id,
            )
            self.runner.prepared[run_id] = PreparedReplay(
                self.observed,
                dataset,
                self.repository.database.source_id,
                stream_id,
                first.sequence,
            )
            if viewer:
                self.viewer_runs.add(run_id)
            return result

    def _make_prepared_room(self) -> None:
        if len(self.runner.prepared) < 3:
            return
        candidates = [
            run_id
            for run_id in self.runner.prepared
            if run_id != self.runner.active_id
            and self.repository.status(run_id)["status"] in TERMINAL
        ]
        if not candidates:
            candidates = [
                run_id
                for run_id in self.runner.prepared
                if run_id in self.viewer_runs
                and run_id != self.runner.active_id
                and self.repository.status(run_id)["status"] == "created"
            ]
        if not candidates:
            raise ServiceError(
                "prepared_run_limit", "The simulator is busy; stop an unused run and retry.", 409
            )
        evicted_id = candidates[0]
        del self.runner.prepared[evicted_id]
        self.viewer_runs.discard(evicted_id)

    def trajectory(self, run_id: str, start: int, end: int, step: int) -> Trajectory:
        """Return a bounded orbit-only preview from a prepared run.

        Parameters
        ----------
        run_id : str
            Prepared run to inspect.
        start, end : int
            Inclusive elapsed-second bounds within the configured run.
        step : int
            Positive sample spacing in simulated seconds.

        Returns
        -------
        Trajectory
            Earth-fixed position and velocity points for each spacecraft.

        Raises
        ------
        ServiceError
            If the request exceeds one hour, is outside the run, or the
            prepared engine has been released.

        Notes
        -----
        This preview contains no future battery state, power, or scenario truth.
        """
        status = self.repository.status(run_id)
        if (
            not 0 <= start <= end <= status["duration_s"]
            or step < 1
            or end - start > 3600
            or (end - start + step - 1) // step + 1 > 3601
        ):
            raise ServiceError(
                "invalid_trajectory",
                "Trajectory must be within the run and at most one hour / 3601 points per satellite.",
                422,
            )
        if status.get("source_kind") == "observed":
            display = self._configured_orbit(run_id, status)
            try:
                display_samples = configured_orbit_points(
                    display, status["duration_s"], start, end, step
                )
            except EarthOrientationError as error:
                raise ServiceError(
                    "configured_orbit_unavailable",
                    "Pinned Earth-orientation data does not cover this configured orbit.",
                    503,
                ) from error
            return Trajectory(
                run_id=run_id,
                kind="configured_orbit",
                description=display.description
                + (
                    " Orbital elements have been edited by the operator."
                    if display.operator_modified
                    else ""
                ),
                satellites=[
                    SatelliteTrajectory(
                        satellite_id=status["satellites"][0]["satellite_id"],
                        samples=display_samples,
                    )
                ],
            )
        prepared = self.runner.prepared.get(run_id)
        if prepared is None or isinstance(prepared, PreparedReplay):
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
                            sun_position_itrs_m=s.sun_position_itrf_m,
                            gcrs_to_itrs_rotation=s.gcrs_to_itrs_rotation,
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
        if not isinstance(prepared, PreparedRun):
            raise ValueError("Physics demonstration requires a simulation engine")
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

    def create_viewer_template_run(
        self,
        path: Path,
        session_lifetime_s: int = 7200,
        *,
        user_id: str | None = None,
        viewer_expires_at: float | None = None,
    ) -> dict[str, Any]:
        """Prepare an independent browser run from the public deployment template.

        Parameters
        ----------
        path : Path
            Server-owned configuration file.
        session_lifetime_s : int, default=7200
            Cookie lifetime used to retain recoverable created runs.
        user_id : str or None
            Stable mock operator identity; omitted for anonymous legacy grants.
        viewer_expires_at : float or None
            Absolute expiry shared by this run and its signed session cookie.

        Returns
        -------
        dict[str, Any]
            Created public run status.
        """
        with self.mutations:
            if user_id is not None:
                for run_id, owner in self.repository.expired_operator_runs(time.time()):
                    self.stop_viewer_run(run_id, owner)
            expired = self.repository.prune_abandoned_viewer_runs(session_lifetime_s * 2)
            for run_id in expired:
                self.runner.prepared.pop(run_id, None)
                self.viewer_runs.discard(run_id)
            config = load_configuration(path.read_text())
            # Private scenario is never copied into an interactive user's revision.
            config = load_configuration(
                json.dumps(config.model_copy(update={"scenario": ()}).model_dump(mode="json")),
                "json",
            )
            key = str(uuid4())
            revision = self.create_configuration(
                config,
                (
                    "viewer:template:configuration",
                    key,
                    canonical_hash(config.model_dump(mode="json")),
                ),
            )
            data_source: Literal["physics", "satellitecots"] = (
                "satellitecots" if len(self.observed.list_datasets()) == 1 else "physics"
            )
            return self.create_run(
                revision["configuration_id"],
                False,
                ("viewer:template:run", key, canonical_hash(revision)),
                viewer=True,
                user_id=user_id,
                viewer_expires_at=viewer_expires_at,
                data_source=data_source,
            )

    def stop_viewer_run(
        self, run_id: str, user_id: str, *, actor_user_id: str | None = None
    ) -> None:
        """Stop an owned run for explicit logout or automatic lease expiration.

        Parameters
        ----------
        run_id : str
            Run scoped by the authenticated viewer session.
        user_id : str
            Mock identity that must match the private run owner.
        actor_user_id : str or None
            Verified human initiating logout. Omit for automatic lease expiry.

        Notes
        -----
        Created and terminal runs retain their history unchanged. A run that
        completes while the stop is queued is already safe to leave alone.
        Persistence failures propagate so logout never claims failed cleanup.
        """
        with self.mutations:
            try:
                run = self.repository.private_run(run_id)
            except ServiceError as error:
                if error.code == "run_not_found":
                    return
                raise
            if run["user_id"] != user_id or actor_user_id not in {None, user_id}:
                raise ServiceError("forbidden", "Viewer session belongs to another operator.", 403)
            if run["status"] not in {"running", "paused"}:
                return
            try:
                self.runner.command(
                    run_id,
                    "stop",
                    None,
                    (
                        "viewer:logout" if actor_user_id is not None else "viewer:expire",
                        run_id,
                        canonical_hash({"action": "stop"}),
                    ),
                    user_id=actor_user_id,
                )
            except ServiceError as error:
                if (
                    error.code != "invalid_transition"
                    or self.repository.status(run_id)["status"] not in TERMINAL
                ):
                    raise

    def ensure_public_demo(self, path: Path) -> str:
        """Keep one bounded shared demo running and expire terminal history.

        Parameters
        ----------
        path : Path
            Validated configuration file for the hosted demonstration.

        Returns
        -------
        str
            Run identifier of the current public demonstration.
        """
        with self.mutations:
            run_id = self.demo_run_id
            if run_id is not None:
                status = self.repository.status(run_id)
                if status["status"] == "running":
                    return run_id
                if status["status"] in {"created", "paused"}:
                    action = "start" if status["status"] == "created" else "resume"
                    self.runner.command(
                        run_id,
                        action,
                        None,
                        ("public:demo", f"{run_id}:{action}", canonical_hash({"action": action})),
                    )
                    return run_id
                if status["status"] not in TERMINAL:
                    raise ServiceError("demo_unavailable", "Public demo is unavailable.", 503)
            expired = self.repository.expire_terminal(days=0)
            run_id = self.prepare_demo(path)
            self.runner.command(
                run_id,
                "start",
                None,
                ("public:demo", f"{run_id}:start", canonical_hash({"action": "start"})),
            )
            logger.info("public_demo_started", extra={"run_id": run_id, "expired_runs": expired})
            return run_id

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
