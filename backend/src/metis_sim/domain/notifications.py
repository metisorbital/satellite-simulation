"""Private, operator-scoped notification contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NotificationModel(BaseModel):
    """Base strict model for notification API data."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class OperatorNotification(NotificationModel):
    """One visible warning or open investigation notification.

    Attributes
    ----------
    key : str
        Stable server-created notification identity.
    version : int
        Material lifecycle version used by per-operator read receipts.
    category : {"warning", "case"}
        The visible workspace item category.
    satellite_id : str
        Selected spacecraft in the warning or investigation workspace.
    title, summary : str
        Public warning copy or operator-authored case summary.
    source : {"telemetry", "model_prediction", "operator_case"}
        Distinguish a committed measurement from a saved model prediction.
    severity : {"warning", "critical", "info"}
        Presentation urgency; critical predictions can trigger the alert banner.
    case_id : str or None
        Existing investigation to review instead of creating a duplicate case.
    """

    key: str = Field(min_length=1, max_length=256)
    version: int = Field(ge=1)
    category: Literal["warning", "case"]
    satellite_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=512)
    summary: str = Field(min_length=1, max_length=4000)
    unread: bool
    source: Literal["telemetry", "model_prediction", "operator_case"] = "telemetry"
    severity: Literal["warning", "critical", "info"] = "warning"
    case_id: str | None = None


class NotificationList(NotificationModel):
    """Visible items and their per-operator unread count."""

    items: list[OperatorNotification]
    unread_count: int = Field(ge=0)


class MarkNotificationReadRequest(NotificationModel):
    """Explicit acknowledgement of one visible notification version."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, allow_inf_nan=False)

    key: str = Field(min_length=1, max_length=256)
    version: int = Field(ge=1)
