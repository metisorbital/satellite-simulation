"""Allowlisted summaries of already committed measurement windows."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from metis_sim.domain.public import PublicModel, PublicModelProvenance

NumericSummary = float | list[float] | None


class ChannelSummary(PublicModel):
    """Summarize valid numeric readings without filling missing observations.

    Notes
    -----
    Min/max/mean are elementwise for vectors and include the initial sample.
    Interval integrals and weighted means exclude zero-duration samples and
    exclude saturated/invalid/missing readings. Counts still retain every quality.
    """

    channel_id: str
    unit: str
    sampling_semantics: str
    valid_count: int = 0
    missing_count: int = 0
    invalid_count: int = 0
    saturated_count: int = 0
    minimum: NumericSummary = None
    maximum: NumericSummary = None
    mean: NumericSummary = None
    interval_integral: NumericSummary = None
    interval_weighted_mean: NumericSummary = None
    valid_interval_duration_s: float = 0.0


class StreamSummary(PublicModel):
    """Report retained coverage and channel quality for one satellite stream.

    Notes
    -----
    ``complete_window`` describes coverage of the selected committed window,
    not completion of the entire configured run.
    """

    source_id: str
    stream_id: str
    satellite_id: str
    catalog_version: str
    frame_count: int
    expected_frame_count: int
    complete_window: bool
    first_sequence: int | None
    last_sequence: int | None
    first_observed_at: datetime | None
    last_observed_at: datetime | None
    channels: list[ChannelSummary]


class TelemetryReport(PublicModel):
    """Summarize a fixed committed boundary without exposing evaluator truth.

    Notes
    -----
    The watermark and stream identities also define a reproducible public
    export boundary. Consumers must retain the run identity for dataset grouping.
    """

    schema_version: Literal["telemetry-report.v1"] = "telemetry-report.v1"
    run_id: str
    run_status: str
    source_kind: Literal["synthetic"] = "synthetic"
    time_domain: Literal["simulation_utc"] = "simulation_utc"
    committed_tick: int
    from_sequence: int
    through_sequence: int
    nominal_cadence_s: Literal[1] = 1
    model_provenance: PublicModelProvenance
    streams: list[StreamSummary]
    limitations: list[str] = Field(
        default_factory=lambda: [
            "Synthetic measurements from declared approximate models; not flight-calibrated telemetry.",
            "Missing channels are not zeros. Unsupported channels carry no invented values.",
            "Interval integrals have channel-unit seconds; endpoint fields are not integrated.",
            "Quaternion component statistics are not an attitude average.",
            "Keep related runs together when creating training, validation and test groups.",
        ]
    )
