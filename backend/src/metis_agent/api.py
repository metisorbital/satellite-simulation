"""Recorded mission planning, durable decisions and host-owned operator workflow."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from fastapi import APIRouter, Request

from metis_agent.briefing import Decision
from metis_agent.models import (
    ApprovalWindow,
    DemoResult,
    MetisBriefing,
    MissionState,
    PlanRuns,
    RunOutcome,
)
from metis_agent.outcome import recorded_outcome
from metis_agent.store import MetisError


@dataclass(frozen=True)
class Viewer:
    """Signed-in operator and authorized replay.

    Attributes
    ----------
    user_id, run_id, display_name : str
        Operator identity, authorized run and public display name.
    """

    user_id: str
    run_id: str
    display_name: str


class MissionStore(Protocol):
    """Durable host storage for serializable per-run mission snapshots."""

    def get(self, run_id: str, user_id: str) -> dict[str, Any] | None:
        """Read one operator-owned mission snapshot."""
        ...

    def save(self, run_id: str, user_id: str, state: dict[str, Any]) -> None:
        """Persist one operator-owned mission snapshot."""
        ...

    def list_pending(self) -> list[dict[str, Any]]:
        """Read this host's durable mission records still waiting for their alert."""
        ...


class MetisHost(Protocol):
    """Identity, public replay status and authorized pacing supplied by the host."""

    def viewer(self, request: Request) -> Viewer:
        """Resolve the authorized operator and replay."""
        ...

    def csrf(self, request: Request, viewer: Viewer) -> None:
        """Validate CSRF for the authenticated operator."""
        ...

    def run_status(self, run_id: str) -> Mapping[str, Any]:
        """Return committed public replay status."""
        ...

    def resume(self, run_id: str, user_id: str, decision: str) -> None:
        """Resume an authorized paused replay after a durable decision."""
        ...

    def set_hold(self, run_id: str, tick: int | None) -> None:
        """Set or clear an alert hold while the recorded replay is not running.

        Parameters
        ----------
        run_id : str
            Current authorized replay.
        tick : int or None
            Absolute source tick, or None to clear the model hold.
        """
        ...


class Metis:
    """Attach the saved forecast and planning scenario to the existing replay.

    Parameters
    ----------
    decision : Decision
        Source-aligned saved forecast and unchanged planner output.
    store : MissionStore
        Durable mission snapshots, keyed by run and operator.
    host : MetisHost
        Public run status, identity and replay pacing.
    alert_s : int, default=3600
        Configured alert offset from mission T0 in recorded source seconds.
    """

    def __init__(
        self, decision: Decision, store: MissionStore, host: MetisHost, alert_s: int = 3600
    ) -> None:
        self.decision, self.store, self.host = decision, store, host
        self.alert_s = alert_s
        self._lock = threading.RLock()
        self._watching: dict[str, tuple[str, int]] = {}
        self._tracking: dict[str, tuple[str, int]] = {}
        self._controls: set[str] = set()
        self.on_mission_result: Callable[[dict[str, Any], Mapping[str, Any]], None] | None = None
        self.on_mission_alert: Callable[[dict[str, Any], Mapping[str, Any]], str] | None = None

    @contextmanager
    def case_workflow(self) -> Iterator[None]:
        """Serialize a case mutation with its mission decision projection.

        Yields
        ------
        None
            The caller validates, writes the case, and synchronizes the mission
            in the same synchronous worker thread.
        """
        with self._lock:
            yield

    @contextmanager
    def control_workflow(self, run_id: str) -> Iterator[None]:
        """Prevent preference changes while an interactive control is in flight.

        Parameters
        ----------
        run_id : str
            Authorized replay receiving Start or Resume.

        Yields
        ------
        None
            The caller prepares under ``case_workflow`` and waits for the writer
            outside its lock, allowing committed callbacks to acquire that lock.
        """
        with self._lock:
            if run_id in self._controls:
                raise MetisError(
                    "control_pending", "Wait for the current replay control to finish."
                )
            self._controls.add(run_id)
        try:
            yield
        finally:
            with self._lock:
                self._controls.discard(run_id)

    def source_compatible(self, status: Mapping[str, Any]) -> bool:
        """Return whether the replay matches this saved prediction's source window.

        Parameters
        ----------
        status : mapping
            Public replay status and original source epoch.

        Returns
        -------
        bool
            True only for BUPT-1 playback beginning at the saved mission origin.
        """
        epoch = datetime.fromisoformat(str(status["epoch_utc"]).replace("Z", "+00:00"))
        origin = datetime.fromisoformat(self.decision.mission.t0_utc.replace("Z", "+00:00"))
        start_s = int((origin - epoch).total_seconds())
        craft = status["satellites"]
        return (
            status.get("source_kind") == "observed"
            and len(craft) == 1
            and str(craft[0]["satellite_id"]).upper() == "BUPT-1"
            and int(status.get("playback_start_s", 0)) == start_s
            and start_s + round(self.decision.mission.duration_min * 60) <= status["duration_s"]
        )

    def attach_run(
        self, user_id: str, run_id: str, status: Mapping[str, Any], alert_min: float
    ) -> dict[str, Any]:
        """Persist mission snapshots for a compatible replay before Start.

        Parameters
        ----------
        user_id, run_id : str
            Authorized operator and existing recorded run.
        status : mapping
            Public status whose playback origin must match the saved forecast.
        alert_min : float
            Mission minute when the original plan forecast requires review.

        Returns
        -------
        dict
            Durable mission state, including the absolute source alert tick.

        Raises
        ------
        MetisError
            When the source or replay origin does not match the saved prediction.
        """
        with self._lock:
            current = self.store.get(run_id, user_id)
            if current is not None:
                self._track_result(current)
                if current["status"] == "watching" and current.get("enabled", True):
                    self._watching[run_id] = (user_id, int(current["alert_at_s"]))
                return current
            epoch = datetime.fromisoformat(str(status["epoch_utc"]).replace("Z", "+00:00"))
            origin = datetime.fromisoformat(self.decision.mission.t0_utc.replace("Z", "+00:00"))
            start_s = int((origin - epoch).total_seconds())
            craft = status["satellites"]
            if not self.source_compatible(status):
                raise MetisError(
                    "mission_source_mismatch",
                    "This saved BUPT-1 prediction requires recorded playback from "
                    f"{self.decision.mission.t0_utc}; select that source time for the mission.",
                )
            state = {
                "schema_version": "recorded-mission.v1",
                "run_id": run_id,
                "user_id": user_id,
                "satellite_id": craft[0]["satellite_id"],
                "mission_epoch_utc": self.decision.mission.t0_utc,
                "mission_start_s": start_s,
                "mission": self.decision.mission.model_dump(mode="json"),
                "forecast": self.decision.forecast.model_dump(mode="json"),
                "proposal": self.decision.proposal.model_dump(mode="json"),
                "proposal_id": self.decision.proposal.proposal_id,
                "plan": "original",
                "tasks": [task.model_dump() for task in self.decision.plan_tasks("original")],
                "status": "watching",
                "enabled": True,
                "alert_at_s": start_s + round(alert_min * 60),
                "alert": {"state": "pending", "raised_at_min": alert_min, "decided_by": None},
                "case_id": None,
                "approval_opened_at": None,
                "approved_plan": None,
                "outcome_basis": "demo_projection",
                "demo_result": None,
            }
            self.store.save(run_id, user_id, state)
            self._watching[run_id] = (user_id, state["alert_at_s"])
            self._track_result(state)
            return state

    def set_enabled(
        self, user_id: str, run_id: str, enabled: bool, request_key: str
    ) -> MissionState:
        """Persist model watching before Start or while paused before the alert.

        Parameters
        ----------
        user_id, run_id : str
            Authorized operator and current recorded replay.
        enabled : bool
            Whether the saved prediction can hold the replay and create a case.
        request_key : str
            Run-scoped idempotency key. Repeated requests never undo later choices.

        Returns
        -------
        MissionState
            Current durable public mission summary.

        Raises
        ------
        MetisError
            If a decision is pending, replay is running, or the forecast decision
            boundary has passed. An existing case cannot be bypassed by disabling.
        """
        with self._lock:
            status = self.host.run_status(run_id)
            state = self.store.get(run_id, user_id)
            if state is not None:
                prior = state.get("preference_requests", {}).get(request_key)
                if prior is not None:
                    previous_enabled = prior["enabled"] if isinstance(prior, dict) else prior
                    if previous_enabled != enabled:
                        raise MetisError(
                            "idempotency_conflict",
                            "This preference key was already used with another value.",
                        )
                    return (
                        MissionState.model_validate(prior["response"])
                        if isinstance(prior, dict)
                        else self._summary({**state, "enabled": prior})
                    )
                reached = int(status["committed_tick"]) >= state["alert_at_s"]
                if state["status"] == "awaiting_decision" or (
                    state["status"] == "watching" and state.get("enabled", True) and reached
                ):
                    raise MetisError(
                        "case_approval_required",
                        "Decide in the attached operator case before changing Metis.",
                    )
                if reached or state["status"] != "watching":
                    raise MetisError(
                        "mission_preference_closed",
                        "Metis can be changed only before this mission's alert boundary.",
                    )
            if run_id in self._controls:
                raise MetisError(
                    "control_pending", "Wait for the current replay control to finish."
                )
            if status["status"] == "running":
                raise MetisError("pause_required", "Pause the replay before changing Metis.")
            if status["status"] not in {"created", "paused"}:
                raise MetisError(
                    "mission_preference_closed",
                    "This replay can no longer change its Metis preference.",
                )
            if state is None:
                state = self.attach_run(user_id, run_id, status, self.alert_s / 60)
            state["enabled"] = enabled
            response = self._summary(state)
            state.setdefault("preference_requests", {})[request_key] = {
                "enabled": enabled,
                "response": response.model_dump(mode="json"),
            }
            self.store.save(run_id, user_id, state)
            if enabled:
                self._watching[run_id] = (user_id, int(state["alert_at_s"]))
            else:
                self._watching.pop(run_id, None)
            self.host.set_hold(run_id, int(state["alert_at_s"]) if enabled else None)
            return self._summary(state)

    @staticmethod
    def _summary(state: Mapping[str, Any]) -> MissionState:
        return MissionState.model_validate(
            {key: state[key] for key in MissionState.model_fields if key in state}
        )

    def _track_result(self, state: Mapping[str, Any]) -> None:
        if state.get("demo_result") is None:
            downlink = next(task for task in state["tasks"] if task["task_id"] == "downlink")
            self._tracking[state["run_id"]] = (
                state["user_id"],
                state["mission_start_s"] + downlink["end_s"],
            )

    def _record_result(self, status: Mapping[str, Any]) -> None:
        run_id = str(status["run_id"])
        tracking = self._tracking.get(run_id)
        if tracking is None or int(status["committed_tick"]) < tracking[1]:
            return
        with self._lock:
            state = self.store.get(run_id, tracking[0])
            if state is None or state.get("demo_result") is not None:
                self._tracking.pop(run_id, None)
                return
            outcome = recorded_outcome(state, status)
            elapsed = tracking[1] - state["mission_start_s"]
            result = DemoResult(
                result="delivered"
                if outcome.delivered_at_min is not None
                else ("capture_failed" if outcome.capture == "skipped" else "missed_delivery"),
                plan=state["plan"],
                recorded_at_utc=(
                    datetime.fromisoformat(state["mission_epoch_utc"].replace("Z", "+00:00"))
                    + timedelta(seconds=elapsed)
                )
                .isoformat()
                .replace("+00:00", "Z"),
                capture=outcome.capture,
                downlink=outcome.downlink,
                delivered_at_min=outcome.delivered_at_min,
            )
            state["demo_result"] = result.model_dump(mode="json")
            if self.on_mission_result is None:
                raise RuntimeError("recorded mission result audit is not configured")
            self.on_mission_result(state, status)
            self.store.save(run_id, tracking[0], state)
            self._tracking.pop(run_id, None)

    def recover(self) -> dict[str, int]:
        """Reconcile committed alert boundaries after host run recovery.

        Returns
        -------
        dict of str to int
            Alert holds for any still-resumable replay. Terminal missions retain
            history and recover a missing case link without claiming a live alert.
        """
        holds: dict[str, int] = {}
        for state in self.store.list_pending():
            run_id, user_id = state["run_id"], state["user_id"]
            status = dict(self.host.run_status(run_id))
            terminal = status["status"] in {"completed", "stopped", "failed", "aborted"}
            self._track_result(state)
            if not state.get("enabled", True):
                self._record_result(status)
                state = self.store.get(run_id, user_id) or state
                self._watching.pop(run_id, None)
                if terminal and state.get("demo_result") is None:
                    state["status"] = "interrupted"
                    self.store.save(run_id, user_id, state)
                continue
            self._watching[run_id] = (user_id, int(state["alert_at_s"]))
            if int(status["committed_tick"]) >= state["alert_at_s"]:
                self.committed(status)
                state = self.store.get(run_id, user_id) or state
            elif not terminal:
                holds[run_id] = int(state["alert_at_s"])
            if terminal and state.get("demo_result") is None:
                with self._lock:
                    state["status"] = "interrupted"
                    self.store.save(run_id, user_id, state)
                    self._watching.pop(run_id, None)
        return holds

    def committed(self, status: dict[str, Any]) -> None:
        """Create the durable operator case only after the alert tick commits.

        Parameters
        ----------
        status : dict
            Status acknowledged by the authoritative replay writer.
        """
        run_id = str(status["run_id"])
        watched = self._watching.get(run_id)
        if watched is not None and int(status["committed_tick"]) >= watched[1]:
            with self._lock:
                state = self.store.get(run_id, watched[0])
                if (
                    state is not None
                    and state["status"] == "watching"
                    and state.get("enabled", True)
                ):
                    if self.on_mission_alert is None:
                        raise RuntimeError("recorded mission case workflow is not configured")
                    # Deterministic case identity makes a retry after a failed snapshot
                    # save recover the same case before recording any demo result.
                    state["case_id"] = self.on_mission_alert(state, status)
                    state["status"] = "awaiting_decision"
                    state["approval_opened_at"] = datetime.now(UTC).isoformat()
                    self.store.save(run_id, watched[0], state)
                self._watching.pop(run_id, None)
        self._record_result(status)

    def validate_case_resolution(
        self, run_id: str, user_id: str, case_id: str, decision: str
    ) -> dict[str, Any]:
        """Validate a standard case decision before its audit record is written.

        Parameters
        ----------
        run_id, user_id, case_id : str
            Authorized mission and its attached operator case.
        decision : str
            ``approved``, ``rejected`` or ``pending`` for a revision.

        Returns
        -------
        dict
            Current durable mission state.
        """
        state = self.store.get(run_id, user_id)
        if state is None or state.get("case_id") != case_id:
            raise MetisError(
                "mission_case_mismatch", "This case does not own the mission decision."
            )
        if decision not in {"approved", "rejected", "pending", "reviewed"}:
            raise MetisError("invalid_mission_decision", "Unsupported mission case decision.")
        target = {
            "approved": "approved",
            "rejected": "dismissed",
            "pending": "awaiting_decision",
            "reviewed": "reviewed",
        }[decision]
        status = self.host.run_status(run_id)
        if state["status"] != target and int(status["committed_tick"]) > state["alert_at_s"]:
            raise MetisError(
                "mission_already_continued", "The replay has continued beyond this decision."
            )
        return state

    def resolve_case(
        self, run_id: str, user_id: str, case_id: str, decision: str, operator: str
    ) -> dict[str, Any]:
        """Apply an audited standard case decision to the same recorded run.

        Parameters
        ----------
        run_id, user_id, case_id : str
            Authorized mission and its attached operator case.
        decision : str
            ``approved`` applies the saved plan, ``rejected`` retains the original,
            and ``pending`` leaves the replay held for a revised recommendation.
        operator : str
            Deciding operator's display name.

        Returns
        -------
        dict
            Persisted mission state. No recorded measurement is changed.
        """
        with self._lock:
            state = self.validate_case_resolution(run_id, user_id, case_id, decision)
            approved = decision == "approved"
            state["plan"] = "metis" if approved else "original"
            state["tasks"] = []
            for task in state["mission"]["tasks"]:
                start = (
                    state["proposal"]["to_start_min"]
                    if approved and task["movable"]
                    else task["start_min"]
                )
                state["tasks"].append(
                    {
                        "task_id": task["task_id"],
                        "start_s": round(start * 60),
                        "end_s": round((start + task["end_min"] - task["start_min"]) * 60),
                        "added_load_w": task["added_load_w"],
                    }
                )
            state["status"] = {
                "approved": "approved",
                "rejected": "dismissed",
                "pending": "awaiting_decision",
                "reviewed": "reviewed",
            }[decision]
            state["alert"]["state"] = {
                "approved": "approved",
                "rejected": "dismissed",
                "pending": "pending",
                "reviewed": "dismissed",
            }[decision]
            state["alert"]["decided_by"] = operator if decision != "pending" else None
            if approved and state.get("approved_plan") is None:
                state["approved_plan"] = {
                    "proposal_id": state["proposal_id"],
                    "approved_by": operator,
                    "approved_at": datetime.now(UTC).isoformat(),
                    "tasks": state["tasks"],
                }
            elif not approved:
                state["approved_plan"] = None
            self.store.save(run_id, user_id, state)
        if decision != "pending":
            self.host.resume(run_id, user_id, decision)
        return state

    def router(self, host: MetisHost) -> APIRouter:
        """Build read-only mission views and reject obsolete bypass actions.

        Parameters
        ----------
        host : MetisHost
            Authenticated host adapter.

        Returns
        -------
        APIRouter
            Existing briefing and outcome URLs with durable recorded semantics.
        """
        router = APIRouter(prefix="/v1/metis", tags=["metis"])

        @router.get("/briefing", response_model=MetisBriefing)
        def briefing(request: Request) -> MetisBriefing:
            """Read the saved forecast and this replay's durable mission state."""
            viewer = host.viewer(request)
            state = self.store.get(viewer.run_id, viewer.user_id)
            d = self.decision
            now = datetime.now(UTC).isoformat()
            approved = state.get("approved_plan") if state else None
            return MetisBriefing(
                mission=state["mission"] if state else d.mission,
                forecast=state["forecast"] if state else d.forecast,
                proposal=state["proposal"] if state else d.proposal,
                window=ApprovalWindow(
                    state="approved" if approved else "closed",
                    opened_at=state.get("approval_opened_at") or now if state else now,
                    closes_at=now,
                    remaining_s=0,
                    approved_by=approved["approved_by"] if approved else None,
                    approved_at=approved["approved_at"] if approved else None,
                ),
                runs=PlanRuns(
                    metis_off=viewer.run_id if state and not state.get("enabled", True) else None,
                    metis_on=viewer.run_id if state and state.get("enabled", True) else None,
                ),
                mission_state=self._summary(state) if state else None,
                metis_enabled=state.get("enabled", True) if state else True,
                alert_at_min=state["alert"]["raised_at_min"] if state else self.alert_s / 60,
                alert_at_utc=(
                    datetime.fromisoformat(
                        (state["mission_epoch_utc"] if state else d.mission.t0_utc).replace(
                            "Z", "+00:00"
                        )
                    )
                    + timedelta(
                        seconds=(state["alert_at_s"] - state["mission_start_s"])
                        if state
                        else self.alert_s
                    )
                )
                .isoformat()
                .replace("+00:00", "Z"),
                mission_available=state is not None
                or self.source_compatible(host.run_status(viewer.run_id)),
                unavailable_reason=None
                if state is not None or self.source_compatible(host.run_status(viewer.run_id))
                else (
                    "Saved model prediction is available only for BUPT-1 replay starting at "
                    f"{d.mission.t0_utc}. Recorded playback remains available."
                ),
            )

        @router.get("/runs/{run_id}/outcome", response_model=RunOutcome)
        def outcome(run_id: str, request: Request) -> RunOutcome:
            """Return forecast projections paced by this replay, never measured execution."""
            viewer = host.viewer(request)
            if run_id != viewer.run_id:
                raise MetisError("run_forbidden", "This session is scoped to another replay.", 403)
            state = self.store.get(run_id, viewer.user_id)
            if state is None:
                raise MetisError("run_not_found", "No recorded mission for this operator.", 404)
            return recorded_outcome(state, host.run_status(run_id))

        @router.post("/proposals/{proposal_id}/approve")
        @router.post("/proposals/{proposal_id}/reopen")
        @router.post("/runs/{proposal_id}/dismiss")
        def case_required(proposal_id: str, request: Request) -> None:
            """Require decisions through the standard operator case audit workflow."""
            viewer = host.viewer(request)
            host.csrf(request, viewer)
            raise MetisError(
                "case_approval_required", "Review and decide in the attached operator case."
            )

        return router
