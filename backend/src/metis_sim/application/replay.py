"""Recorded telemetry adapter for the existing durable run writer."""

from typing import Any
from uuid import UUID

from metis_sim.adapters.observed import ObservedRepository
from metis_sim.adapters.records import utc_now
from metis_sim.application.errors import ServiceError
from metis_sim.application.satellitecots_measurement import project_satellitecots_channels
from metis_sim.domain.observed import ObservedDataset, ObservedSample
from metis_sim.domain.telemetry import MeasurementFrame


class PreparedReplay:
    """Read bounded source pages and project only observations due on the clock.

    Parameters
    ----------
    repository : ObservedRepository
        Read-only access to the imported, immutable archive.
    dataset : ObservedDataset
        Source identity, original epoch and catalog mapping.
    source_id, stream_id : str
        Registered replay producer and newly allocated stream identities.
    start_sequence : int, default=0
        Original row selected by a seek. Its first emitted sequence is zero.

    Notes
    -----
    Neither gaps nor unsupported channels receive synthetic substitute values.
    The private page cache may contain upcoming readings; only ``frames_through``
    creates public frames and its elapsed-time bound is the runner's clock.
    """

    def __init__(
        self,
        repository: ObservedRepository,
        dataset: ObservedDataset,
        source_id: str,
        stream_id: str,
        start_sequence: int = 0,
    ) -> None:
        self.repository = repository
        self.dataset = dataset
        self.source_id = source_id
        self.stream_id = UUID(stream_id)
        self.start_sequence = start_sequence
        self._after = start_sequence - 1
        self._samples: list[ObservedSample] = []

    def frames_through(self, elapsed_s: int) -> list[dict[str, Any]]:
        """Project original samples at or before a committed clock candidate.

        Parameters
        ----------
        elapsed_s : int
            Inclusive elapsed source-time bound selected by the runner.

        Returns
        -------
        list of dict
            Ordered immutable frame candidates. The runner persists the whole
            result atomically and retries the same values on storage failure.

        Notes
        -----
        Page reads complete before advancing the local cursor. A failed read
        can therefore be retried without skipping any observations.
        """
        samples = list(self._samples)
        after = samples[-1].sequence if samples else self._after
        while not samples or samples[-1].elapsed_s <= elapsed_s:
            page = self.repository.read_samples(self.dataset.dataset_id, after, 1024)
            if not page:
                if after < self.dataset.sample_count - 1:
                    raise ServiceError(
                        "dataset_incomplete",
                        "Recorded observations are unavailable before archive end.",
                        503,
                    )
                break
            if page[0].sequence != after + 1:
                raise ServiceError(
                    "dataset_incomplete", "Recorded observations contain a sequence gap.", 503
                )
            samples.extend(page)
            after = page[-1].sequence
        due = [sample for sample in samples if sample.elapsed_s <= elapsed_s]
        emitted_at = utc_now()
        frames = [
            MeasurementFrame.model_validate(
                dict(
                    schema_version="telemetry.v1",
                    source_id=self.source_id,
                    stream_id=self.stream_id,
                    sequence=sample.sequence - self.start_sequence,
                    satellite_id=self.dataset.satellite_id,
                    source_kind="observed",
                    time_domain="mission_utc",
                    observed_at=sample.observed_at,
                    sample_window_s=0.0,
                    emitted_at=emitted_at,
                    catalog_version=self.dataset.catalog_version,
                    mode=None,
                    interval_mode=None,
                    channels=project_satellitecots_channels(
                        dict(zip(self.dataset.columns, sample.readings, strict=True))
                    ),
                )
            ).model_dump(mode="json")
            for sample in due
        ]
        if due:
            self._after = due[-1].sequence
        self._samples = samples[len(due) :]
        return frames
