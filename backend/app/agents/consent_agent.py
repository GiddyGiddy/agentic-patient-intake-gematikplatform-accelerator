from app.agents.state import IntakeState


def consent_node(state: IntakeState) -> IntakeState:
    """Gatekeeper for TI access (ePA medication plan, KIS, KIM).

    Without consent the workflow stops and the frontend must obtain approval via Gesundheits-ID.
    """
    if state.get("consent_granted"):
        return {"iam_required": False, "next_agent": "SchedulingAgent"}
    return {
        "iam_required": True,
        "iam_message": "Bitte geben Sie den Zugriff auf Ihre ePA-Daten über Ihre Gesundheits-ID frei.",
        "next_agent": "ConsentAgent",
    }
