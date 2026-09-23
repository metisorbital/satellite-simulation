"""One-way allowlisted measurement mapping and observable event transitions."""

from dataclasses import asdict
from typing import Any
from uuid import UUID

from metis_sim.adapters.records import utc_now
from metis_sim.domain.config import SimulationConfig
from metis_sim.domain.physics import PhysicsSample
from metis_sim.domain.telemetry import ChannelReading, MeasurementFrame, OperationalEvent


class MeasurementProjector:
    """Track only public transition state, independent of private scenario outcomes.

    Parameters
    ----------
    config : SimulationConfig
        Validated profile limits and satellite definitions.
    source_id : str
        Producer identity.
    streams : dict
        Satellite to stream UUID bindings allocated for this execution.
    """

    def __init__(self, config: SimulationConfig, source_id: str, streams: dict[str, str]) -> None:
        self.source_id = source_id
        self.streams = streams
        self.modes: dict[str, str] = {}
        self.unserved: dict[str, bool] = {}
        self.sequences = {satellite: 0 for satellite in streams}
        self.limits = {
            s.satellite_id: config.profiles[s.profile_id].public_limits for s in config.satellites
        }
        self.active_limits: dict[tuple[str, int], bool] = {}

    def project(
        self, samples: tuple[PhysicsSample, ...]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Project one tick into public records and separate private truth.

        Parameters
        ----------
        samples : tuple of PhysicsSample
            Physical endpoints for the tick in stable satellite order. These
            samples contain private truth and must not be serialized directly.

        Returns
        -------
        tuple of list of dict
            Public telemetry frames, public operational events, and private
            evaluation rows, in that order. The caller persists them together
            at one committed boundary.

        Notes
        -----
        Only allowlisted physical channels enter public frames. Private scenario
        settings and outcomes remain in the third collection.
        """
        frames, events, truth = [], [], []
        emitted_at = utc_now()
        for sample in samples:
            envelope = dict(
                source_id=self.source_id,
                stream_id=UUID(self.streams[sample.satellite_id]),
                satellite_id=sample.satellite_id,
                source_kind="synthetic",
                time_domain="simulation_utc",
                observed_at=sample.observed_at,
                emitted_at=emitted_at,
            )
            frame = MeasurementFrame.model_validate(
                dict(
                    **envelope,
                    schema_version="telemetry.v1",
                    catalog_version="power-leo.v1",
                    sequence=sample.tick,
                    sample_window_s=float(sample.sample_window_s),
                    mode=sample.mode,
                    interval_mode=sample.interval_mode,
                    channels={
                        name: ChannelReading.model_validate(dict(value=value, quality="valid"))
                        for name, value in sample.public_channels().items()
                    },
                )
            )
            frames.append(frame.model_dump(mode="json"))
            for event_type, reason, details in self._transitions(sample):
                event = OperationalEvent.model_validate(
                    dict(
                        **envelope,
                        schema_version="operational_event.v1",
                        event_sequence=self.sequences[sample.satellite_id],
                        event_type=event_type,
                        reason_code=reason,
                        details=details,
                    )
                )
                events.append(event.model_dump(mode="json"))
                self.sequences[sample.satellite_id] += 1
            truth.append(
                {
                    **asdict(sample.truth),
                    "satellite_id": sample.satellite_id,
                    "sequence": sample.tick,
                    "tick": sample.tick,
                    "observed_at": sample.observed_at.isoformat(),
                    "battery_energy_wh": sample.battery_energy_wh,
                    "right_censored": None,
                    "terminal_reason": None,
                }
            )
        return frames, events, truth

    def _transitions(self, sample: PhysicsSample) -> list[tuple[str, str, dict[str, Any]]]:
        satellite = sample.satellite_id
        events: list[tuple[str, str, dict[str, Any]]] = []
        previous_mode = self.modes.get(satellite)
        if previous_mode is not None and previous_mode != sample.mode:
            events.append(
                (
                    "mode_changed",
                    "scheduled_operation",
                    {"from_mode": previous_mode, "to_mode": sample.mode},
                )
            )
        self.modes[satellite] = sample.mode
        unserved = sample.unserved_power_w > 0
        if unserved != self.unserved.get(satellite, False):
            events.append(
                (
                    "power_unserved",
                    "observed_power_balance",
                    dict(
                        active=unserved,
                        value_w=sample.unserved_power_w,
                        sample_window_s=float(sample.sample_window_s),
                    ),
                )
            )
        self.unserved[satellite] = unserved
        for index, limit in enumerate(self.limits[satellite]):
            key = (satellite, index)
            active = self.active_limits.get(key, False)
            if limit.operator == "lt":
                updated = sample.battery_soc < (limit.clear_value if active else limit.value)
            else:
                updated = sample.battery_soc > (limit.clear_value if active else limit.value)
            if updated != active:
                event_type = "low_energy_limit_entered" if updated else "low_energy_limit_cleared"
                events.append(
                    (event_type, "configured_public_limit", limit.model_dump(mode="json"))
                )
            self.active_limits[key] = updated
        return events
