"""Private, operator-authored case workflow contracts.

Cases deliberately contain only operator narrative and snapshots of already
committed public telemetry. They never project a private manifest, truth,
future state, prediction, or command.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CasePriority = Literal["monitor", "review", "urgent"]
CaseStatus = Literal["open", "closed"]
CaseDecision = Literal["pending", "approved", "rejected", "revised"]
CaseOutcome = Literal["awaiting_observation", "supported", "corrected", "inconclusive"]
CaseActivityKind = Literal[
    "created", "assessment", "recommendation", "decision", "outcome", "evidence"
]


class CaseModel(BaseModel):
    """Base model for immutable private case wire contracts."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CaseRequest(CaseModel):
    """Base model for strict, browser-supplied private case commands."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, allow_inf_nan=False)


class CaseEvidenceReading(CaseModel):
    """One typed reading rendered from an immutable public channel catalog.

    Attributes
    ----------
    channel_id : str
        Public catalog channel identifier.
    value_text : str
        Canonical textual representation of the committed public value.
    quality : {"valid", "missing", "invalid", "saturated"}
        Public measurement-quality state at the committed sample.
    unit : str
        Unit from the matching immutable channel catalog definition.
    """

    channel_id: str = Field(min_length=1, max_length=128)
    value_text: str = Field(min_length=1, max_length=512)
    quality: Literal["valid", "missing", "invalid", "saturated"]
    unit: str = Field(min_length=1, max_length=64)


class CaseEvidence(CaseModel):
    """Server-captured snapshot of exactly one committed public frame.

    Attributes
    ----------
    source_id, stream_id, satellite_id, payload_hash : str or UUID
        Public producer, stream, and spacecraft provenance.
    sequence : int
        Committed stream sequence used for the immutable capture.
    observed_at, emitted_at, committed_at, captured_at : datetime
        Public producer and storage provenance plus the capture time.
    catalog_version : str
        Versioned public catalog used to derive reading units.
    source_kind, time_domain : str
        Public origin and timestamp semantics from the measurement envelope.
    readings : list of CaseEvidenceReading
        Allowlisted committed channel readings only.
    """

    source_id: str = Field(min_length=1, max_length=64)
    stream_id: UUID
    satellite_id: str = Field(min_length=1, max_length=64)
    payload_hash: str = Field(min_length=64, max_length=64)
    sequence: int = Field(ge=0, le=9_007_199_254_740_991)
    observed_at: datetime
    emitted_at: datetime
    committed_at: datetime
    captured_at: datetime
    catalog_version: Literal["power-leo.v1", "spacecraft.v1", "satellitecots.v1"]
    source_kind: Literal["synthetic", "observed"]
    time_domain: Literal["simulation_utc", "mission_utc"]
    readings: list[CaseEvidenceReading] = Field(max_length=128)


class CaseActivity(CaseModel):
    """Append-only audit activity attributed to the authenticated operator.

    Attributes
    ----------
    activity_id, case_id, user_id : UUID
        Activity, containing case, and authenticated author identities.
    kind : str
        Server-defined workflow action category.
    text : str
        Server-authored audit text; authored substantive content remains on the case.
    created_at : datetime
        Server-recorded activity timestamp.
    evidence : CaseEvidence or None
        Optional later committed public-frame snapshot.
    """

    activity_id: UUID
    case_id: UUID
    user_id: UUID
    kind: CaseActivityKind
    text: str
    created_at: datetime
    evidence: CaseEvidence | None


class CaseRecord(CaseModel):
    """Private operator case with revision-controlled workflow state.

    Attributes
    ----------
    case_id, run_id, user_id : UUID
        Case, logical originating run, and owner identities.
    satellite_id : str
        Spacecraft identity from the selected public stream.
    title, summary : str
        Operator-authored investigation heading and context.
    priority, status : str
        Operator urgency and case lifecycle state.
    assessment, missing_information, recommendation, expected_effect, tradeoffs : str
        Operator-authored review material; no automatic diagnosis is generated.
    decision, decision_reason : str
        Human review state and explanation.
    outcome, outcome_notes : str
        Observation result and optional narrative distinct from approval.
    revision : int
        Monotonic optimistic-concurrency version.
    created_at, updated_at : datetime
        Server-recorded case lifecycle timestamps.
    evidence : CaseEvidence or None
        Immutable initial public-frame snapshot, if one was captured at creation.
    activities : list of CaseActivity
        Bounded chronological audit history.
    activity_count : int
        Total append-only activity count, including entries outside this response.
    activities_truncated : bool
        Whether older activities exist beyond the returned bounded history.
    """

    case_id: UUID
    run_id: UUID
    user_id: UUID
    satellite_id: str = Field(min_length=1, max_length=64)
    title: str
    summary: str
    priority: CasePriority
    status: CaseStatus
    assessment: str
    missing_information: str
    recommendation: str
    expected_effect: str
    tradeoffs: str
    decision: CaseDecision
    decision_reason: str
    outcome: CaseOutcome
    outcome_notes: str
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    evidence: CaseEvidence | None
    activities: list[CaseActivity] = Field(max_length=50)
    activity_count: int = Field(ge=0)
    activities_truncated: bool


class CaseSummary(CaseModel):
    """Lightweight private case projection for bounded historical lists.

    Attributes
    ----------
    case_id, run_id, user_id : UUID
        Case, logical originating run, and owning operator identities.
    satellite_id : str
        Spacecraft identity from the selected public stream.
    title, summary : str
        Operator-authored investigation heading and context.
    priority, status, decision, outcome : str
        Current operator-managed workflow state.
    revision : int
        Current optimistic-concurrency version.
    created_at, updated_at : datetime
        Server-recorded lifecycle timestamps.
    """

    case_id: UUID
    run_id: UUID
    user_id: UUID
    satellite_id: str
    title: str
    summary: str
    priority: CasePriority
    status: CaseStatus
    decision: CaseDecision
    outcome: CaseOutcome
    revision: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class CaseList(CaseModel):
    """Bounded private case list for the authenticated named operator.

    Attributes
    ----------
    items : list of CaseSummary
        At most 100 most-recently updated owned case records.
    total : int
        Total owned case count before the response cap.
    has_more : bool
        Whether older owned cases exist beyond this response.
    """

    items: list[CaseSummary] = Field(max_length=100)
    total: int = Field(ge=0)
    has_more: bool


class CreateCaseRequest(CaseRequest):
    """Create an operator case for one satellite in the current owned run.

    Attributes
    ----------
    satellite_id : str
        Public stream spacecraft identity.
    title, summary : str
        Nonblank operator-authored investigation text.
    priority : {"monitor", "review", "urgent"}
        Operator-selected triage level.
    sequence : int or None
        Exact committed stream sequence to capture; omit for the current tail.
    """

    satellite_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1, max_length=8000)
    priority: CasePriority
    sequence: int | None = Field(default=None, ge=0, le=9_007_199_254_740_991)

    @field_validator("title", "summary")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        """Reject whitespace-only operator narrative."""
        if not value.strip():
            raise ValueError("Case text must contain a non-whitespace character")
        return value


class AssessmentCaseRequest(CaseRequest):
    """Replace the assessment fields at an expected case revision."""

    revision: int = Field(ge=1)
    assessment: str = Field(max_length=8000)
    missing_information: str = Field(max_length=8000)


class RecommendationCaseRequest(CaseRequest):
    """Replace an operator-authored recommendation at an expected revision."""

    revision: int = Field(ge=1)
    recommendation: str = Field(max_length=8000)
    expected_effect: str = Field(max_length=8000)
    tradeoffs: str = Field(max_length=8000)

    @field_validator("recommendation")
    @classmethod
    def nonblank_recommendation(cls, value: str) -> str:
        """Require an authored recommendation before it can be reviewed."""
        if not value.strip():
            raise ValueError("Recommendation must contain a non-whitespace character")
        return value


class DecisionCaseRequest(CaseRequest):
    """Record a human decision at an expected case revision."""

    revision: int = Field(ge=1)
    decision: Literal["approved", "rejected", "revised"]
    reason: str = Field(max_length=8000)
    revised_recommendation: str | None = Field(default=None, max_length=8000)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        """Require a human decision explanation."""
        if not value.strip():
            raise ValueError("Decision reason must contain a non-whitespace character")
        return value

    @model_validator(mode="after")
    def validate_revised_recommendation(self) -> "DecisionCaseRequest":
        """Require revised text only for a revised decision."""
        if self.decision == "revised" and not (self.revised_recommendation or "").strip():
            raise ValueError("A revised decision requires revised_recommendation")
        if self.decision != "revised" and self.revised_recommendation is not None:
            raise ValueError("revised_recommendation is only valid for a revised decision")
        return self


class OutcomeCaseRequest(CaseRequest):
    """Record a later observation outcome, optionally closing the case."""

    revision: int = Field(ge=1)
    outcome: CaseOutcome
    outcome_notes: str = Field(max_length=8000)
    close_case: bool

    @model_validator(mode="after")
    def require_notes_for_observed_outcome(self) -> "OutcomeCaseRequest":
        """Require an authored observation narrative once an outcome is known."""
        if self.outcome != "awaiting_observation" and not self.outcome_notes.strip():
            raise ValueError("Observed outcomes require nonblank outcome_notes")
        return self


class CaptureCaseEvidenceRequest(CaseRequest):
    """Capture the current committed public sample for an expected revision."""

    revision: int = Field(ge=1)


__all__ = [
    "AssessmentCaseRequest",
    "CaptureCaseEvidenceRequest",
    "CaseActivity",
    "CaseEvidence",
    "CaseEvidenceReading",
    "CaseList",
    "CaseRecord",
    "CaseSummary",
    "CreateCaseRequest",
    "DecisionCaseRequest",
    "OutcomeCaseRequest",
    "RecommendationCaseRequest",
]
