"""Bounded-memory descriptive statistics for public committed telemetry."""

from dataclasses import dataclass, field
from typing import Any

from metis_sim.domain.catalog import ChannelDefinition
from metis_sim.domain.reports import ChannelSummary


@dataclass
class ChannelAccumulator:
    """Accumulate quality counts and componentwise numeric statistics.

    Parameters
    ----------
    definition : ChannelDefinition
        Versioned public metadata for this one channel.

    Notes
    -----
    Only valid numeric values enter statistics. Saturated values remain counted
    separately rather than silently being treated as reliable measurements.
    """

    definition: ChannelDefinition
    counts: dict[str, int] = field(
        default_factory=lambda: dict(valid=0, missing=0, invalid=0, saturated=0)
    )
    minimum: list[float] | None = None
    maximum: list[float] | None = None
    mean: list[float] | None = None
    integral: list[float] | None = None
    weight: float = 0.0
    numeric_count: int = 0

    def add(self, reading: dict[str, Any] | None, duration_s: float) -> None:
        """Observe one reading without resampling, imputing or changing its quality.

        Parameters
        ----------
        reading : dict or None
            Original public reading; absent catalog channels count as missing.
        duration_s : float
            Completed interval length; zero at the initial sample.
        """
        quality = reading["quality"] if reading else "missing"
        self.counts[quality] += 1
        value = reading["value"] if reading else None
        if quality != "valid" or value is None or isinstance(value, str):
            return
        values = [float(x) for x in value] if isinstance(value, (list, tuple)) else [float(value)]
        self.numeric_count += 1
        if self.minimum is None:
            self.minimum = values.copy()
            self.maximum = values.copy()
            self.mean = values.copy()
        else:
            assert self.maximum is not None and self.mean is not None
            for index, item in enumerate(values):
                self.minimum[index] = min(self.minimum[index], item)
                self.maximum[index] = max(self.maximum[index], item)
                self.mean[index] += (item - self.mean[index]) / self.numeric_count
        if self.definition.sampling_semantics == "interval_mean" and duration_s > 0:
            if self.integral is None:
                self.integral = [0.0] * len(values)
            for index, item in enumerate(values):
                self.integral[index] += item * duration_s
            self.weight += duration_s

    def result(self) -> ChannelSummary:
        """Produce the allowlisted summary for the observed window.

        Returns
        -------
        ChannelSummary
            Statistics with nulls when there were no suitable observations.
        """

        def shape(value: list[float] | None) -> float | list[float] | None:
            """Restore scalar or vector shape from an internal accumulator."""
            if value is None:
                return None
            return value[0] if self.definition.value_type == "scalar" else value

        weighted = (
            [v / self.weight for v in self.integral] if self.integral and self.weight else None
        )
        return ChannelSummary(
            channel_id=self.definition.channel_id,
            unit=self.definition.unit,
            sampling_semantics=self.definition.sampling_semantics,
            **{f"{quality}_count": count for quality, count in self.counts.items()},
            minimum=shape(self.minimum),
            maximum=shape(self.maximum),
            mean=shape(self.mean),
            interval_integral=shape(self.integral),
            interval_weighted_mean=shape(weighted),
            valid_interval_duration_s=self.weight,
        )
