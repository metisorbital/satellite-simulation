"""Private operator Shift Log contracts, separate from public telemetry."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from metis_sim.domain.public import Action, RunState

EntryKind = Literal["note", "decision", "action", "unresolved_issue", "event"]


class ShiftLogModel(BaseModel):
    """Allowlist private draft and shared submitted records for named operators.

    Notes
    -----
    These contracts are excluded from the consumer telemetry schema.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ShiftLogEntryDetails(ShiftLogModel):
    """Describe an automatically recorded successful simulator control.

    Attributes
    ----------
    action : str or None
        Authenticated simulator command; absent for manually entered records.
    speed : int or None
        Requested simulation speed for a speed change.
    committed_tick : int or None
        Durable simulation boundary at command acknowledgement.
    status : str or None
        Resulting run state at that boundary.
    """

    action: Action | None = None
    speed: int | None = None
    committed_tick: int | None = None
    status: RunState | None = None


class ShiftLogEntry(ShiftLogModel):
    """An immutable entry attributed to exactly one registered operator.

    Attributes
    ----------
    entry_id, shift_id, user_id : UUID
        Entry identity, containing shift, and authenticated author.
    kind : str
        Note, decision, action, unresolved issue, or observed event.
    text : str
        Operator narrative or server-authored control description.
    details : ShiftLogEntryDetails
        Allowlisted command context; empty for manual entries.
    created_at : datetime
        Server-recorded UTC entry time.
    """

    entry_id: UUID
    shift_id: UUID
    user_id: UUID
    kind: EntryKind
    text: str
    details: ShiftLogEntryDetails
    created_at: datetime


class ShiftLog(ShiftLogModel):
    """An operator's editable draft or frozen submitted shift record.

    Attributes
    ----------
    shift_id, run_id, user_id : UUID
        Shift, simulation run, and owning operator identities.
    status : {"draft", "submitted"}
        Whether entries and summary may still be changed.
    summary : str
        Operator-edited handover narrative.
    created_at, updated_at, submitted_at : datetime or None
        Server-recorded UTC lifecycle times; submission is initially absent.
    entries : list of ShiftLogEntry
        Chronologically ordered records attributed to their authors.
    """

    shift_id: UUID
    run_id: UUID
    user_id: UUID
    status: Literal["draft", "submitted"]
    summary: str
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    entries: list[ShiftLogEntry]


class ShiftLogList(ShiftLogModel):
    """Return authorized drafts and retained submitted handovers.

    Attributes
    ----------
    items : list of ShiftLog
        Authorized shift records with their entries.
    """

    items: list[ShiftLog]


class AddShiftLogEntryRequest(ShiftLogModel):
    """Accept a bounded narrative without client-controlled attribution.

    Attributes
    ----------
    kind : str
        Record category selected by the operator.
    text : str
        Nonblank narrative of at most 4,000 characters.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    kind: EntryKind
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        """Reject blank narratives while preserving the operator's text.

        Parameters
        ----------
        value : str
            Bounded submitted text.

        Returns
        -------
        str
            Original text when it contains a non-whitespace character.

        Raises
        ------
        ValueError
            If the narrative is whitespace only.
        """
        if not value.strip():
            raise ValueError("Entry text must contain a non-whitespace character")
        return value


class UpdateShiftLogSummaryRequest(ShiftLogModel):
    """Replace a draft's handover summary.

    Attributes
    ----------
    summary : str
        Narrative of at most 12,000 characters; may be cleared.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    summary: str = Field(max_length=12000)


class SubmitShiftLogRequest(ShiftLogModel):
    """Accept an empty submission command without identity or state claims.

    Notes
    -----
    The server freezes the draft identified by the authorized route.
    """

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
