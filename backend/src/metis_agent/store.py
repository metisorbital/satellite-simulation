"""In-memory approval state per operator; lost on restart by design."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from metis_agent.models import ApprovalWindow, ApprovedPlan, TaskWindow


class MetisError(Exception):
    """Actionable Metis API error.

    Parameters
    ----------
    code : str
        Stable machine-readable code.
    message : str
        Public explanation.
    status : int
        HTTP status.
    """

    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _utc(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, UTC).isoformat().replace("+00:00", "Z")


@dataclass
class _Decision:
    proposal_id: str
    opened_at: float
    plan: ApprovedPlan | None = None


class DecisionStore:
    """Approval windows and approved plans, keyed by operator.

    Parameters
    ----------
    window_s : float
        Length of the approval window before T0, in wall-clock seconds.
    clock : callable, default=time.time
        Wall clock in seconds.
    """

    def __init__(self, window_s: float, clock: Callable[[], float] = time.time) -> None:
        self.window_s, self.clock = window_s, clock
        self._lock = threading.Lock()
        self._decisions: dict[str, _Decision] = {}

    def _decision(self, user_id: str, proposal_id: str) -> _Decision:
        current = self._decisions.get(user_id)
        if current is None or current.proposal_id != proposal_id:
            current = self._decisions[user_id] = _Decision(proposal_id, self.clock())
        return current

    def window(self, user_id: str, proposal_id: str) -> ApprovalWindow:
        """Return the operator's window, opening it on first view.

        Parameters
        ----------
        user_id : str
            Operator identity.
        proposal_id : str
            Proposal being reviewed.

        Returns
        -------
        ApprovalWindow
            Open, approved, or closed after the window elapses.
        """
        with self._lock:
            decision = self._decision(user_id, proposal_id)
            return self._window(decision)

    def _window(self, decision: _Decision) -> ApprovalWindow:
        closes = decision.opened_at + self.window_s
        remaining = max(0.0, closes - self.clock())
        plan = decision.plan
        state: Literal["open", "approved", "closed"] = (
            "approved" if plan else ("open" if remaining > 0 else "closed")
        )
        return ApprovalWindow(
            state=state,
            opened_at=_utc(decision.opened_at),
            closes_at=_utc(closes),
            remaining_s=round(remaining, 1) if plan is None else 0.0,
            approved_by=plan.approved_by if plan else None,
            approved_at=plan.approved_at if plan else None,
        )

    def approve(
        self, user_id: str, proposal_id: str, approver: str, tasks: list[TaskWindow]
    ) -> ApprovedPlan:
        """Record approval while the window is open; repeat calls return the same plan.

        Parameters
        ----------
        user_id : str
            Operator identity.
        proposal_id : str
            Proposal being approved.
        approver : str
            Operator display name.
        tasks : list of TaskWindow
            Task windows the Metis plan flies.

        Returns
        -------
        ApprovedPlan
            The recorded approval.

        Raises
        ------
        MetisError
            ``uplink_closed`` after the window elapsed.
        """
        with self._lock:
            decision = self._decision(user_id, proposal_id)
            if decision.plan is not None:
                return decision.plan
            if self.clock() >= decision.opened_at + self.window_s:
                raise MetisError(
                    "uplink_closed",
                    "The planning uplink closed before approval; reopen to rehearse.",
                )
            decision.plan = ApprovedPlan(
                proposal_id=proposal_id,
                approved_by=approver,
                approved_at=_utc(self.clock()),
                tasks=tasks,
            )
            return decision.plan

    def reopen(self, user_id: str, proposal_id: str) -> ApprovalWindow:
        """Clear approval and restart the window, for rehearsals.

        Parameters
        ----------
        user_id : str
            Operator identity.
        proposal_id : str
            Proposal under review.

        Returns
        -------
        ApprovalWindow
            A newly opened window.
        """
        with self._lock:
            self._decisions[user_id] = _Decision(proposal_id, self.clock())
            return self._window(self._decisions[user_id])

    def approved(self, user_id: str, proposal_id: str) -> ApprovedPlan:
        """Return the operator's approved plan.

        Parameters
        ----------
        user_id : str
            Operator identity.
        proposal_id : str
            Approved proposal.

        Returns
        -------
        ApprovedPlan
            The approval record.

        Raises
        ------
        MetisError
            ``not_approved`` when the operator has not approved this proposal.
        """
        with self._lock:
            decision = self._decisions.get(user_id)
            if decision is None or decision.proposal_id != proposal_id or decision.plan is None:
                raise MetisError(
                    "not_approved", "Approve the proposal before flying the Metis plan.", 409
                )
            return decision.plan
