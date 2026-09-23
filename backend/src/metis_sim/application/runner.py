"""Single-owner fixed-step runner with durable command acknowledgements."""

import logging
import queue
import threading
import time
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from metis_sim.adapters.repository import TERMINAL, Idempotent, Repository
from metis_sim.application.errors import ServiceError
from metis_sim.application.measurement import MeasurementProjector
from metis_sim.domain.config import SimulationConfig
from metis_sim.logging import safe_sqlstate
from metis_sim.models.engine import SimulationEngine

logger = logging.getLogger(__name__)


@dataclass
class PreparedRun:
    """One exclusively owned run's immutable geometry and public transition state."""

    config: SimulationConfig
    engine: SimulationEngine
    projector: MeasurementProjector


@dataclass
class PendingCommand:
    """Serialize application and cancellation to prevent late unacknowledged actions.

    Parameters
    ----------
    run_id : str
        Run receiving the requested action.
    action : str
        Validated control action.
    speed : int or None
        Requested speed for a ``set_speed`` action.
    token : Idempotent
        Identity of the durable acknowledgement.
    deadline : float
        Expiry in seconds on the owning runner's monotonic clock.
    """

    run_id: str
    action: str
    speed: int | None
    token: Idempotent
    deadline: float
    lock: threading.Lock = field(default_factory=threading.Lock)
    phase: str = "queued"
    result: Future[dict[str, Any]] = field(default_factory=Future)


class Runner:
    """Pace integer ticks in one thread and publish only committed state.

    Parameters
    ----------
    repository : Repository
        Transactional writer port.
    paced : bool, default=True
        False removes wall pacing for deterministic offline validation.
    capacity_check : callable, optional
        Raise when storage capacity or writer ownership prevents advancement.
    monotonic : callable, default=time.monotonic
        Read wall time in seconds. One clock controls pacing and deadlines.
    wait : callable, default=threading.Event.wait
        Wait for an event or a wall-time timeout. Tests may advance the injected
        clock here without sleeping.
    """

    def __init__(
        self,
        repository: Repository,
        paced: bool = True,
        capacity_check: Callable[[], None] | None = None,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        wait: Callable[[threading.Event, float], bool] = threading.Event.wait,
    ) -> None:
        self.repository = repository
        self.paced = paced
        self.capacity_check = capacity_check
        self._monotonic = monotonic
        self._wait = wait
        self.prepared: dict[str, PreparedRun] = {}
        self.commands: queue.Queue[PendingCommand] = queue.Queue(maxsize=32)
        self.stop_event = threading.Event()
        self.wakeup = threading.Event()
        self._retry_delay = threading.Event()
        self.thread = threading.Thread(target=self._loop, name="metis-writer", daemon=True)
        self.active_id: str | None = None
        self.backpressure = False
        self.failure: str | None = None
        self._next_due = self._pace_wall = self._metrics_wall = self._monotonic()
        self._pace_tick = -1
        self._metrics_tick = -1

    def start(self) -> None:
        """Start the single writer after migrations, lock acquisition and recovery."""
        self.thread.start()

    def command(
        self, run_id: str, action: str, speed: int | None, token: Idempotent
    ) -> dict[str, Any]:
        """Acknowledge only durable commands, cancelling unapplied requests by deadline."""
        try:
            existing = self.repository.existing(token)
        except SQLAlchemyError:
            raise ServiceError(
                "control_not_applied", "Storage is unavailable; command was not applied.", 503
            ) from None
        if existing is not None:
            return existing
        if self.backpressure or self.failure:
            raise ServiceError(
                "control_not_applied", "Persistence is unavailable; command was not applied.", 503
            )
        command = PendingCommand(run_id, action, speed, token, self._monotonic() + 5)
        try:
            self.commands.put_nowait(command)
        except queue.Full as error:
            raise ServiceError(
                "control_not_applied", "Control queue is full; retry with the same key.", 503
            ) from error
        self.wakeup.set()
        try:
            return command.result.result(timeout=max(0, command.deadline - self._monotonic()))
        except TimeoutError:
            with command.lock:
                if command.phase == "queued":
                    command.phase = "cancelled"
                    raise ServiceError(
                        "control_not_applied", "Command expired before application.", 503
                    ) from None
            # It crossed the application boundary before expiry. Its transaction
            # determines the acknowledgement; returning 'unapplied' here would lie.
            return command.result.result()

    def close(self) -> None:
        """Stop at the current commit boundary and finalize active-run censoring."""
        self.stop_event.set()
        self.wakeup.set()
        if self.thread.is_alive():
            self.thread.join(timeout=35)

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            self._drain_commands()
            if self.active_id and not self.failure:
                try:
                    run_id = self.active_id
                    status = self._retry_persistence(
                        partial(self.repository.status, run_id), run_id
                    )
                    if status["status"] == "running":
                        self._advance(status)
                        continue
                except Exception as error:
                    self._fail(error)
            self._wait(self.wakeup, 0.05)
            self.wakeup.clear()
        if self.active_id and not self.failure:
            try:
                run_id = self.active_id
                status = self._retry_persistence(partial(self.repository.status, run_id), run_id)
                self._terminal(status, "stopped")
            except Exception as error:
                self._fail(error)
        self._reject_queued()

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                return
            with command.lock:
                if command.phase == "cancelled":
                    continue
                if self._monotonic() > command.deadline or self.backpressure or self.failure:
                    command.phase = "cancelled"
                    command.result.set_exception(
                        ServiceError("control_not_applied", "Command was not applied.", 503)
                    )
                    continue
                command.phase = "applying"
            try:
                result = self._apply(command)
                command.result.set_result(result)
            except SQLAlchemyError:
                command.result.set_exception(
                    ServiceError(
                        "control_not_applied",
                        "Storage is unavailable; command was not applied.",
                        503,
                    )
                )
            except Exception as error:
                command.result.set_exception(error)
            finally:
                command.phase = "done"

    def _apply(self, command: PendingCommand) -> dict[str, Any]:
        existing = self.repository.existing(command.token)
        if existing is not None:
            return existing
        status = self.repository.status(command.run_id)
        state, action = status["status"], command.action
        previous_speed = status["requested_speed"]
        if state in TERMINAL:
            raise ServiceError("terminal_run", "Terminal runs cannot restart; create a new run.")
        if action == "start":
            if state != "created":
                raise ServiceError("invalid_transition", "Only a created run can start.")
            if self.active_id and self.active_id != command.run_id:
                raise ServiceError(
                    "active_run_exists", "Stop the active run before starting another."
                )
            if command.run_id not in self.prepared:
                raise ServiceError("run_not_prepared", "Prepare this run before starting.", 503)
            status["status"] = "running"
        elif action == "pause":
            if state not in {"running", "paused"}:
                raise ServiceError("invalid_transition", "Pause requires a running run.")
            status.update(status="paused", effective_speed=0)
        elif action == "resume":
            if state not in {"paused", "running"}:
                raise ServiceError("invalid_transition", "Resume requires a paused run.")
            status["status"] = "running"
        elif action == "stop":
            if state not in {"running", "paused"}:
                raise ServiceError("invalid_transition", "Stop requires a running or paused run.")
            return self._terminal(status, "stopped", command.token)
        elif action == "set_speed":
            if command.speed not in {1, 5, 20}:
                raise ServiceError("invalid_speed", "Speed must be 1, 5, or 20.", 422)
            status["requested_speed"] = command.speed
        else:
            raise ServiceError("invalid_action", "Unsupported control action.", 422)
        result = self._commit(status, [], [], [], command.token)
        if status["status"] in {"running", "paused"}:
            self.active_id = command.run_id
        if status["status"] == "running" and (
            state != "running" or status["requested_speed"] != previous_speed
        ):
            self._next_due = self._pace_wall = self._metrics_wall = self._monotonic()
            self._pace_tick = self._metrics_tick = status["committed_tick"]
        return result

    def _advance(self, status: dict[str, Any]) -> None:
        now = self._monotonic()
        if self.paced and now < self._next_due:
            self._wait(self.wakeup, min(0.05, self._next_due - now))
            self.wakeup.clear()
            return
        run = self.prepared[status["run_id"]]
        start = status["committed_tick"] + 1
        if self.capacity_check is not None and start % 100 < 4:
            self._retry_persistence(self.capacity_check, status["run_id"])
        if start > status["duration_s"]:
            self._terminal(status, "completed")
            return
        # Four complete ticks / 200ms at most, never omit initial t=0.
        count = min(4, max(1, status["requested_speed"] // 5)) if self.paced else 4
        end = min(status["duration_s"], start + count - 1)
        frames, events, truth = [], [], []
        for tick in range(start, end + 1):
            f, e, t = run.projector.project(run.engine.sample(tick))
            frames.extend(f)
            events.extend(e)
            truth.extend(t)
        elapsed = max(1e-9, now - self._metrics_wall)
        effective = max(0.0, (end - self._metrics_tick) / elapsed)
        if elapsed < 0.5:
            effective = status["effective_speed"]
        else:
            self._metrics_wall, self._metrics_tick = now, end
        lag = max(
            0.0, (now - self._pace_wall) - (end - self._pace_tick) / status["requested_speed"]
        )
        status.update(
            committed_tick=end,
            committed_at=frames[-1]["observed_at"],
            frame_count=(end + 1) * len(status["satellites"]),
            effective_speed=effective,
            wall_lag_s=lag,
        )
        self._commit(status, frames, events, truth, processing_ms=(self._monotonic() - now) * 1000)
        period = (end - start + 1) / status["requested_speed"]
        next_due = self._next_due + period
        finished = self._monotonic()
        # Ordinary scheduler jitter must not accumulate into permanent slow-down.
        # A missed batch slot, including storage recovery, starts a fresh period
        # instead of spending pacing debt in immediate catch-up batches.
        self._next_due = next_due if finished <= next_due else finished + period
        if end == status["duration_s"]:
            self._terminal(status, "completed")

    def _commit(
        self,
        status: dict[str, Any],
        frames: list,
        events: list,
        truth: list,
        token: Idempotent | None = None,
        processing_ms: float | None = None,
    ) -> dict[str, Any]:
        started = self._monotonic()
        result = self._retry_persistence(
            lambda: self.repository.commit(status, frames, events, truth, token),
            status["run_id"],
            len(frames),
        )
        if frames and status["committed_tick"] % 100 < 4:
            logger.info(
                "batch_committed",
                extra={
                    "run_id": status["run_id"],
                    "tick": status["committed_tick"],
                    "frame_count": len(frames),
                    "commit_ms": (self._monotonic() - started) * 1000,
                    "processing_ms": processing_ms,
                    "queue_depth": self.commands.qsize(),
                    "requested_speed": status["requested_speed"],
                    "effective_speed": status["effective_speed"],
                },
            )
        return result

    def _retry_persistence[T](
        self, operation: Callable[[], T], run_id: str, queue_depth: int = 0
    ) -> T:
        """Retry one storage operation without recomputing physical outputs."""
        deadline = self._monotonic() + 30
        logged_backpressure = False
        while self._monotonic() < deadline:
            try:
                result = operation()
                self.backpressure = False
                if logged_backpressure:
                    logger.info(
                        "persistence_recovered",
                        extra={"run_id": run_id, "queue_depth": queue_depth},
                    )
                return result
            except SQLAlchemyError as error:
                self.backpressure = True
                self._reject_queued()
                if not logged_backpressure:
                    logger.warning(
                        "persistence_backpressure",
                        extra={
                            "run_id": run_id,
                            "queue_depth": queue_depth,
                            "error_type": type(error).__name__,
                            "sqlstate": safe_sqlstate(error),
                        },
                    )
                    logged_backpressure = True
            except ServiceError as error:
                if error.code == "writer_ownership_lost":
                    self.failure = error.code
                    self.backpressure = True
                    self._reject_queued()
                raise
            # Shutdown cannot turn a retry delay into a busy loop. An in-flight
            # batch retains the same retry budget before final recovery policy.
            self._wait(self._retry_delay, min(0.25, max(0, deadline - self._monotonic())))
        self.failure = "persistence_unavailable"
        raise ServiceError(
            "persistence_unavailable", "Storage did not recover; advancement stopped.", 503
        )

    def _terminal(
        self, status: dict[str, Any], state: str, token: Idempotent | None = None
    ) -> dict[str, Any]:
        reason = "duration_reached" if state == "completed" else state
        records = self._retry_persistence(
            lambda: self.repository.final_truth(status["run_id"], reason), status["run_id"]
        )
        status.update(status=state, effective_speed=0)
        result = self._commit(status, [], [], records, token)
        self.active_id = None
        return result

    def _fail(self, error: Exception) -> None:
        diagnostic = error.code if isinstance(error, ServiceError) else "simulation_failed"
        fields: dict[str, Any] = {
            "run_id": self.active_id,
            "error_type": type(error).__name__,
            "error_code": diagnostic,
            "diagnostic": diagnostic,
        }
        if self.active_id and not self.failure:
            try:
                run_id = self.active_id
                status = self._retry_persistence(partial(self.repository.status, run_id), run_id)
                fields.update(tick=status["committed_tick"], status=status["status"])
                status["diagnostic"] = diagnostic
                self._terminal(status, "failed")
            except Exception:
                self.failure = "persistence_unavailable"
        logger.error("runner_failed", extra=fields)
        self.active_id = None

    def _reject_queued(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                return
            with command.lock:
                if command.phase == "queued":
                    command.phase = "cancelled"
                    command.result.set_exception(
                        ServiceError(
                            "control_not_applied",
                            "Persistence is unavailable; command was not applied.",
                            503,
                        )
                    )
