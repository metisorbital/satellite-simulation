"""HTTP routes for the Metis view; the host application supplies identity and data."""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Literal, Protocol

from fastapi import APIRouter, Request

from metis_agent.briefing import PLAN_NAMES, Decision
from metis_agent.models import (
    ApprovalWindow,
    ApprovedPlan,
    MetisAlert,
    MetisBriefing,
    Plan,
    PlanRuns,
    RunOutcome,
    TaskWindow,
)
from metis_agent.outcome import OutcomeTracker
from metis_agent.store import DecisionStore, MetisError


@dataclass(frozen=True)
class Viewer:
    """Signed-in operator and the run their session is scoped to.

    Attributes
    ----------
    user_id : str
        Operator identity.
    run_id : str
        Run bound to the session cookie.
    display_name : str
        Operator name for approval records.
    """

    user_id: str
    run_id: str
    display_name: str


Mode = Literal["metis_off", "metis_on"]


@dataclass(frozen=True)
class _FlownRun:
    user_id: str
    plan: Plan
    tasks: tuple[TaskWindow, ...]
    mode: Mode
    alert: MetisAlert | None


class MetisHost(Protocol):
    """Capabilities the simulator lends to Metis, all over public data."""

    def viewer(self, request: Request) -> Viewer:
        """Return the signed-in operator or raise the host's 401 error."""
        ...

    def csrf(self, request: Request, viewer: Viewer) -> None:
        """Reject a state-changing request without a valid CSRF token."""
        ...

    def run_status(self, run_id: str) -> Mapping[str, Any]:
        """Return the public run status."""
        ...

    def frames(
        self, run_id: str, satellite_id: str, from_sequence: int, through_sequence: int
    ) -> Sequence[Mapping[str, Any]]:
        """Return public telemetry frames for one spacecraft in an inclusive range."""
        ...

    def events(self, run_id: str, satellite_id: str) -> Sequence[Mapping[str, Any]]:
        """Return the public operational events of one spacecraft committed so far."""
        ...


class Metis:
    """The Metis agent: prepared decision, approvals, flown runs and outcomes.

    Parameters
    ----------
    decision : Decision
        Mission, forecast and proposal.
    store : DecisionStore
        Approval windows per operator.
    """

    def __init__(self, decision: Decision, store: DecisionStore) -> None:
        self.decision, self.store, self.tracker = decision, store, OutcomeTracker()
        self._lock = threading.Lock()
        self._runs: dict[str, _FlownRun] = {}
        self._latest: dict[str, dict[Mode, str]] = {}

    def _check(self, proposal_id: str) -> None:
        if proposal_id != self.decision.proposal.proposal_id:
            raise MetisError("proposal_not_found", "Unknown proposal.", 404)

    @staticmethod
    def plan_name(plan: Plan) -> str:
        """Return a plan's display name, used as the spacecraft name of its run.

        Parameters
        ----------
        plan : {"original", "metis"}
            Plan.

        Returns
        -------
        str
            ``Original schedule`` or ``Metis plan``.
        """
        return PLAN_NAMES[plan]

    def plan_windows(self, plan: Plan) -> list[dict[str, Any]]:
        """Return a plan's task windows without checking approval, for warm-up.

        Parameters
        ----------
        plan : {"original", "metis"}
            Plan.

        Returns
        -------
        list of dict
            Task windows with ``task_id``, ``start_s``, ``end_s`` and ``added_load_w``.
        """
        return [task.model_dump() for task in self.decision.plan_tasks(plan)]

    def flight_windows(
        self, user_id: str, plan: Plan, proposal_id: str | None
    ) -> list[dict[str, Any]]:
        """Return the task windows an operator may fly now.

        Parameters
        ----------
        user_id : str
            Operator identity.
        plan : {"original", "metis"}
            Plan to fly.
        proposal_id : str or None
            Approved proposal, required for ``metis``.

        Returns
        -------
        list of dict
            Task windows for the simulator's demo launch.

        Raises
        ------
        MetisError
            ``not_approved`` for the Metis plan without an approval.
        """
        if plan == "original":
            return self.plan_windows("original")
        if proposal_id is None:
            raise MetisError("not_approved", "Approve the proposal before flying the Metis plan.")
        self._check(proposal_id)
        return [task.model_dump() for task in self.store.approved(user_id, proposal_id).tasks]

    def record_run(
        self,
        user_id: str,
        run_id: str,
        plan: Plan,
        windows: Sequence[Mapping[str, Any]],
        *,
        watch: bool,
        alert_min: float,
        operator: str,
    ) -> None:
        """Remember a launched demo run so its outcome and alert can be reported.

        Parameters
        ----------
        user_id : str
            Operator who launched it.
        run_id : str
            New run.
        plan : {"original", "metis"}
            Plan it flies.
        windows : sequence of mapping
            Its task windows.
        watch : bool
            Whether Metis watches it. A watched original run raises a pending
            alert at ``alert_min``, where it pauses, and restarts the approval
            window; a Metis plan run continues the watched run whose alert was
            approved.
        alert_min : float
            Mission minute of the alert.
        operator : str
            Operator display name, recorded on an approved alert.
        """
        tasks = tuple(TaskWindow.model_validate(dict(window)) for window in windows)
        metis_on = watch or plan == "metis"
        alert = None
        if plan == "metis":
            alert = MetisAlert(state="approved", raised_at_min=alert_min, decided_by=operator)
        elif watch:
            alert = MetisAlert(state="pending", raised_at_min=alert_min, decided_by=None)
            self.store.reopen(user_id, self.decision.proposal.proposal_id)
        mode: Mode = "metis_on" if metis_on else "metis_off"
        with self._lock:
            if plan == "metis":
                watched_id = self._latest.get(user_id, {}).get("metis_on", "")
                watched = self._runs.get(watched_id)
                if watched is not None and watched.alert is not None:
                    alert = watched.alert.model_copy(
                        update={"state": "approved", "decided_by": operator}
                    )
                    self._runs[watched_id] = replace(watched, alert=alert)
            self._runs[run_id] = _FlownRun(user_id, plan, tasks, mode, alert)
            self._latest.setdefault(user_id, {})[mode] = run_id

    def _plan_runs(self, user_id: str) -> PlanRuns:
        with self._lock:
            latest = self._latest.get(user_id, {})
            return PlanRuns(metis_off=latest.get("metis_off"), metis_on=latest.get("metis_on"))

    def _reset_runs(self, user_id: str) -> None:
        with self._lock:
            forgotten = [rid for rid, run in self._runs.items() if run.user_id == user_id]
            for run_id in forgotten:
                del self._runs[run_id]
            self._latest.pop(user_id, None)
        self.tracker.forget(forgotten)

    def router(self, host: MetisHost) -> APIRouter:
        """Build the ``/v1/metis`` routes.

        Parameters
        ----------
        host : MetisHost
            Identity, CSRF and public data from the host application.

        Returns
        -------
        APIRouter
            Briefing, approve, reopen, run-outcome and alert-dismiss routes.
        """
        router = APIRouter(prefix="/v1/metis", tags=["metis"])

        def briefing_for(viewer: Viewer) -> MetisBriefing:
            d = self.decision
            return MetisBriefing(
                mission=d.mission,
                forecast=d.forecast,
                proposal=d.proposal,
                window=self.store.window(viewer.user_id, d.proposal.proposal_id),
                runs=self._plan_runs(viewer.user_id),
            )

        @router.get("/briefing", response_model=MetisBriefing)
        def briefing(request: Request) -> MetisBriefing:
            """Return the request, forecast, proposal, approval window and latest runs."""
            return briefing_for(host.viewer(request))

        @router.post("/proposals/{proposal_id}/approve", response_model=ApprovedPlan)
        def approve(proposal_id: str, request: Request) -> ApprovedPlan:
            """Approve the proposal while the planning uplink is open."""
            viewer = host.viewer(request)
            host.csrf(request, viewer)
            self._check(proposal_id)
            return self.store.approve(
                viewer.user_id,
                proposal_id,
                viewer.display_name,
                self.decision.plan_tasks("metis"),
            )

        @router.post("/proposals/{proposal_id}/reopen", response_model=ApprovalWindow)
        def reopen(proposal_id: str, request: Request) -> ApprovalWindow:
            """Clear the approval and both plans' runs, then restart the window."""
            viewer = host.viewer(request)
            host.csrf(request, viewer)
            self._check(proposal_id)
            self._reset_runs(viewer.user_id)
            return self.store.reopen(viewer.user_id, proposal_id)

        def flown_run(run_id: str, viewer: Viewer) -> _FlownRun:
            with self._lock:
                flown = self._runs.get(run_id)
            if flown is None or flown.user_id != viewer.user_id:
                raise MetisError(
                    "run_not_found", "No Metis demo run with this ID for this operator.", 404
                )
            return flown

        def raised(flown: _FlownRun, status: Mapping[str, Any]) -> MetisAlert | None:
            # A pending alert stays hidden until the run reaches it and pauses.
            alert = flown.alert
            if alert is not None and alert.state == "pending":
                if int(status["committed_tick"]) < round(alert.raised_at_min * 60):
                    return None
            return alert

        @router.post("/runs/{run_id}/dismiss", response_model=MetisAlert)
        def dismiss(run_id: str, request: Request) -> MetisAlert:
            """Dismiss the pending alert; the watched run continues its original plan."""
            viewer = host.viewer(request)
            host.csrf(request, viewer)
            flown = flown_run(run_id, viewer)
            alert = raised(flown, host.run_status(run_id))
            if alert is None or alert.state != "pending":
                raise MetisError("alert_not_pending", "This run has no pending Metis alert.")
            alert = alert.model_copy(
                update={"state": "dismissed", "decided_by": viewer.display_name}
            )
            with self._lock:
                self._runs[run_id] = replace(flown, alert=alert)
            return alert

        @router.get("/runs/{run_id}/outcome", response_model=RunOutcome)
        def outcome(run_id: str, request: Request) -> RunOutcome:
            """Return what happened on one of the operator's demo runs, from public data."""
            viewer = host.viewer(request)
            flown = flown_run(run_id, viewer)
            status = host.run_status(run_id)
            return self.tracker.outcome(
                run_id,
                flown.plan,
                PLAN_NAMES[flown.plan],
                status,
                flown.tasks,
                lambda sid, lo, hi: host.frames(run_id, sid, lo, hi),
                lambda sid: host.events(run_id, sid),
                metis_on=flown.mode == "metis_on",
                alert=raised(flown, status),
            )

        return router
