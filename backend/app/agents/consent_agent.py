from app.agents.state import IntakeState
from app.core.epa_client import fetch_medication_plan


def consent_node(state: IntakeState) -> IntakeState:
    """Gatekeeper for TI access (ePA medication plan, KIS, KIM).

    Without consent the workflow stops and the frontend must obtain approval via Gesundheits-ID.
    """
    if state.get("consent_granted"):
        meds, reachable = fetch_medication_plan(state.get("patient_id", ""), state.get("access_token"))
        return {
            "iam_required": False,
            "medication_plan": meds,
            "epa_available": reachable,
            "next_agent": "SchedulingAgent",
        }
    return {
        "iam_required": True,
        "iam_message": "Bitte geben Sie den Zugriff auf Ihre ePA-Daten über Ihre Gesundheits-ID frei.",
        "next_agent": "ConsentAgent",
    }
