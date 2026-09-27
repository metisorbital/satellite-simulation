"""Simulator capabilities lent to the Metis agent: identity, CSRF and public telemetry.

Metis never sees configuration, scenarios or private truth. It reads the same
public run status, telemetry frames and operational events as any consumer.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import Request
from metis_agent.api import Viewer

from metis_sim.application.errors import ServiceError


class SimulatorMetisHost:
    """Adapter from the simulator's app state to the Metis host protocol.

    Parameters
    ----------
    state : Any
        FastAPI ``app.state`` holding ``auth``, ``repository`` and ``reader``.
    """

    def __init__(self, state: Any) -> None:
        self.state = state

    def viewer(self, request: Request) -> Viewer:
        """Return the signed-in mock operator and the run their cookie is scoped to.

        Parameters
        ----------
        request : Request
            Browser request with a viewer session cookie.

        Returns
        -------
        Viewer
            Operator identity, scoped run and display name.

        Raises
        ------
        ServiceError
            401 without a signed-in operator; 403 for other credentials.
        """
        principal = self.state.auth.principal(request)
        principal.require({"viewer_control"})
        if principal.user_id is None or principal.run_id is None:
            raise ServiceError("unauthorized", "Sign in with a demo operator.", 401)
        operator = self.state.auth.operators_by_id.get(principal.user_id)
        name = operator.display_name if operator is not None else "Operator"
        return Viewer(user_id=principal.user_id, run_id=principal.run_id, display_name=name)

    def csrf(self, request: Request, viewer: Viewer) -> None:
        """Reject a state-changing request without the session's CSRF token.

        Parameters
        ----------
        request : Request
            Browser request.
        viewer : Viewer
            Operator already resolved from the same request.
        """
        self.state.auth.csrf(request, self.state.auth.principal(request))

    def run_status(self, run_id: str) -> Mapping[str, Any]:
        """Return the public run status.

        Parameters
        ----------
        run_id : str
            Run authorized for the viewer.

        Returns
        -------
        Mapping
            Public status, including each satellite's capacity and public limits.
        """
        return self.state.repository.status(run_id)

    def frames(
        self, run_id: str, satellite_id: str, from_sequence: int, through_sequence: int
    ) -> Sequence[Mapping[str, Any]]:
        """Return committed public frames for one satellite in an inclusive range.

        Parameters
        ----------
        run_id : str
            Run launched by the viewer.
        satellite_id : str
            Spacecraft whose stream is read.
        from_sequence, through_sequence : int
            Inclusive sequence (tick) bounds, at most 2,000 apart.

        Returns
        -------
        Sequence of Mapping
            Public telemetry frames.
        """
        page = self.state.reader.page(
            self._stream(run_id, satellite_id),
            None,
            through_sequence - from_sequence + 1,
            "telemetry",
            from_sequence=from_sequence,
            through_sequence=through_sequence,
        )
        return page["items"]

    def events(self, run_id: str, satellite_id: str) -> Sequence[Mapping[str, Any]]:
        """Return the committed public operational events of one spacecraft.

        Parameters
        ----------
        run_id : str
            Run launched by the viewer.
        satellite_id : str
            Spacecraft whose events are read.

        Returns
        -------
        Sequence of Mapping
            Public events in sequence order, such as ``operation_skipped``.
        """
        stream_id, items, after = self._stream(run_id, satellite_id), [], None
        while True:
            page = self.state.reader.page(stream_id, after, 500, "events")
            items.extend(page["items"])
            if not page["has_more"]:
                return items
            after = page["next_cursor"]

    def _stream(self, run_id: str, satellite_id: str) -> str:
        status = self.run_status(run_id)
        return str(
            next(s["stream_id"] for s in status["satellites"] if s["satellite_id"] == satellite_id)
        )
