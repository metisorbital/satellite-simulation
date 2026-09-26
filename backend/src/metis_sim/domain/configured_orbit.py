"""Orbit-only display configuration, independent of recorded telemetry channels."""

from datetime import UTC, datetime

from pydantic import Field, field_validator

from metis_sim.domain.config import ContractModel, OrbitConfiguration


class ConfiguredOrbit(ContractModel):
    """Freeze the public basis and assumptions of a configured display orbit.

    Attributes
    ----------
    epoch_utc : datetime
        Epoch assigned to the configured elements, not a measured source epoch.
    orbit : OrbitConfiguration
        Validated classical elements used only for orbit presentation.
    source_url, description : str
        Published parameter source and the limits of its interpretation.
    operator_modified : bool
        Whether the configured elements differ from their packaged defaults.
    """

    epoch_utc: datetime
    orbit: OrbitConfiguration
    source_url: str = Field(min_length=1, max_length=1000)
    description: str = Field(min_length=1, max_length=2000)
    operator_modified: bool = False

    @field_validator("epoch_utc")
    @classmethod
    def require_utc_offset(cls, value: datetime) -> datetime:
        """Normalize the explicit display epoch to UTC.

        Parameters
        ----------
        value : datetime
            Display epoch with a required timezone offset.

        Returns
        -------
        datetime
            The same instant normalized to UTC.
        """
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Configured orbit epoch must include a UTC offset")
        return value.astimezone(UTC)
