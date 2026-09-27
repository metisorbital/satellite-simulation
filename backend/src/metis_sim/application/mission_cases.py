"""Connect saved model predictions to the durable operator investigation workflow."""

from collections.abc import Mapping
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from metis_sim.adapters.cases import CaseRepository
from metis_sim.adapters.records import canonical_hash


def proposal_recommendation(proposal: Mapping[str, Any]) -> str:
    """Render the exact saved proposal reviewed by the operator.

    Parameters
    ----------
    proposal : mapping
        Allowlisted saved model proposal with original and proposed task times.

    Returns
    -------
    str
        Human-readable planning action, without claiming spacecraft execution.
    """
    return (
        f"Move the routine compute batch from +{proposal['from_start_min']:g} "
        f"to +{proposal['to_start_min']:g} minutes in the mission plan."
    )


class MissionCaseBridge:
    """Create a normal investigation once a saved prediction reaches its hold.

    Parameters
    ----------
    cases : CaseRepository
        Existing database-backed case and Shift Log writer.
    """

    def __init__(self, cases: CaseRepository) -> None:
        self.cases = cases

    def raise_alert(self, state: Mapping[str, Any], status: Mapping[str, Any]) -> str:
        """Persist one reviewable prediction and committed evidence idempotently.

        Parameters
        ----------
        state : mapping
            Durable mission snapshot, including owner, source spacecraft,
            proposal and forecast. No realized private scenario data is used.
        status : mapping
            Public status at the successfully committed replay hold.

        Returns
        -------
        str
            Stable case identity, including after a crash or repeated callback.
        """
        run_id, user_id = str(state["run_id"]), str(state["user_id"])
        proposal = state["proposal"]
        forecast = state["forecast"]
        key = f"metis-prediction:{run_id}:{proposal['proposal_id']}"
        case_id = str(uuid5(NAMESPACE_URL, key))
        recommendation = proposal_recommendation(proposal)
        playback = (
            "The replay is paused for an operator decision. "
            if status["status"] == "paused"
            else "The replay ended before this alert was linked; the recovered case remains available for review. "
        )
        summary = (
            f"Saved model prediction for {state['satellite_id']}: {proposal['rationale']}\n\n"
            f"Forecast origin: {forecast['decision_time_source']}. "
            f"Mission T0: {state['mission_epoch_utc']}. "
            f"{playback}This is a saved, "
            "source-aligned model forecast, not a fresh forecast or a measured fault. "
            "Battery reserve and mission loads are planning assumptions; the recording "
            "does not establish task execution, image delivery, or battery state of charge."
        )
        prediction = {
            "recommendation": recommendation,
            "expected_effect": (
                "Preserve the projected energy budget for thermal capture and downlink. "
                f"The saved model projects {proposal['proposed_downlink_start_wh']:.2f} Wh "
                "above the assumed reserve at downlink start. Approval changes the "
                "mission plan and resumes the same recorded stream; it sends no spacecraft command."
            ),
            "tradeoffs": (
                "Routine processing is delayed. Forecast uncertainty and assumed energy "
                "scaling remain; access geometry, link capacity, and actual delivery are "
                "unvalidated. Record an observed outcome separately after review."
            ),
        }
        result = self.cases.create(
            run_id,
            user_id,
            str(state["satellite_id"]),
            "Model prediction: wildfire delivery at risk",
            summary,
            "urgent",
            status.get("committed_sequence"),
            ("model-warning", key, canonical_hash({"run_id": run_id, "proposal": proposal})),
            model_case_id=case_id,
            model_recommendation=prediction,
        )
        return str(result["case_id"])

    def record_result(self, state: Mapping[str, Any], status: Mapping[str, Any]) -> None:
        """Record the illustrative mission result in its case and Shift Log once.

        Parameters
        ----------
        state : mapping
            Durable mission and computed demo result, separate from telemetry.
        status : mapping
            Acknowledged source-clock boundary which reached the scenario result.
        """
        result = state["demo_result"]
        if result["result"] == "delivered":
            narrative = (
                f"The illustrative thermal image reaches the ground at +{result['delivered_at_min']:g} "
                "minutes, enabling the assumed wildfire response briefing."
            )
        elif result["result"] == "capture_failed":
            narrative = "The assumed energy budget prevents thermal capture; no image is delivered."
        else:
            narrative = (
                "The illustrative camera captures the image, but the saved energy budget "
                "cannot support the full downlink window. The modeled admission gate "
                "prevents transmission from starting; ground delivery is missed."
            )
        text = (
            f"DEMO SCENARIO RESULT — {state['satellite_id']} — {result['recorded_at_utc']}\n"
            f"Plan: {result['plan']}; Metis {'on' if state.get('enabled', True) else 'off'}. "
            f"{narrative}\n"
            "Derived from the saved model margin and assumed mission tasks; not measured "
            "BUPT-1 task execution, a received photograph, or a spacecraft command. "
            "The operator's case decision and observed-outcome assessment remain unchanged."
        )
        self.cases.record_demo_result(
            state["run_id"],
            state["user_id"],
            state.get("case_id"),
            text,
            ("mission-demo-result", state["run_id"], canonical_hash(result)),
        )
