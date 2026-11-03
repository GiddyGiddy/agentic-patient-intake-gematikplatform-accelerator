from app.agents.state import IntakeState
from app.core.audit import audit
from app.core.epa_client import fetch_medication_plan


IAM_MESSAGE = "Bitte geben Sie den Zugriff auf Ihre ePA-Daten über Ihre Gesundheits-ID frei."


def consent_node(state: IntakeState) -> IntakeState:
    """Gatekeeper for TI access (ePA medication plan, KIS, KIM).

    Without consent the workflow stops and the frontend must obtain approval via Gesundheits-ID.
    """
    if state.get("consent_granted"):
        pid = state.get("patient_id", "")
        meds, reachable = fetch_medication_plan(pid, state.get("access_token"))
        audit("epa_read", pid, resource="MedicationStatement", count=len(meds), reachable=reachable)
        return {
            "iam_required": False,
            "medication_plan": meds,
            "epa_available": reachable,
            "next_agent": "SchedulingAgent",
        }
    return {
        "iam_required": True,
        "iam_message": IAM_MESSAGE,
        "next_agent": "ConsentAgent",
    }
