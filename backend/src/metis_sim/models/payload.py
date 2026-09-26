"""Deterministic power-gated camera acquisition and finite local storage."""

from __future__ import annotations

import math
from dataclasses import dataclass

from metis_sim.domain.subsystems import PayloadConfiguration


@dataclass(frozen=True, slots=True)
class PayloadSample:
    """Interval power/status and endpoint payload counters.

    Attributes
    ----------
    power_w : float
        Actual payload allocation within the existing served load.
    acquisition_active : bool
        Whether this interval supplied the camera and had room for an image.
    uptime_s, image_count, storage_used_bytes : int
        Consecutive powered active time, cumulative images, and stored bytes.
    """

    power_w: float
    acquisition_active: bool
    uptime_s: int
    image_count: int
    storage_used_bytes: int


class PayloadModel:
    """Advance camera state solely from its mode and supplied power.

    Parameters
    ----------
    config : PayloadConfiguration
        Declared acquisition rate and storage capacity.
    """

    def __init__(self, config: PayloadConfiguration) -> None:
        self._config = config
        self._uptime_s = 0
        self._exposure_s = 0
        self._image_count = 0
        self._storage_bytes = config.initial_storage_bytes

    def step(self, dt_s: float, mode: str, supplied_w: float) -> PayloadSample:
        """Integrate one fully powered exposure interval or reset on interruption.

        Parameters
        ----------
        dt_s : float
            Zero at initialization or one simulated second.
        mode : str
            Mode active throughout the completed interval.
        supplied_w : float
            Nonnegative portion of the existing load allocated to the payload.

        Returns
        -------
        PayloadSample
            Interval operation and endpoint counters. Power loss or leaving
            payload mode resets boot uptime and the incomplete exposure.
        """
        if dt_s not in (0.0, 1.0):
            raise ValueError("Payload dt_s must be zero or one second.")
        if not math.isfinite(supplied_w) or not 0 <= supplied_w <= self._config.active_power_w:
            raise ValueError("Payload supply must be finite and within its declared active power.")
        powered = (
            mode == "payload_active"
            and supplied_w > 0
            and math.isclose(supplied_w, self._config.active_power_w, rel_tol=1e-12, abs_tol=0)
        )
        room = (
            self._storage_bytes + self._config.image_size_bytes
            <= self._config.storage_capacity_bytes
        )
        acquiring = powered and room
        if dt_s:
            if powered:
                self._uptime_s += 1
            else:
                self._uptime_s = 0
            if acquiring:
                self._exposure_s += 1
                if self._exposure_s == self._config.image_period_s:
                    self._storage_bytes += self._config.image_size_bytes
                    self._image_count += 1
                    self._exposure_s = 0
            else:
                self._exposure_s = 0
        return PayloadSample(
            power_w=supplied_w,
            acquisition_active=acquiring,
            uptime_s=self._uptime_s,
            image_count=self._image_count,
            storage_used_bytes=self._storage_bytes,
        )
