from typing import Optional, TypedDict

# Manchester-Triage-System, ordered from most to least urgent
TRIAGE_LEVELS = ["Rot", "Orange", "Gelb", "Grün", "Blau"]


class IntakeState(TypedDict, total=False):
    patient_id: str
    messages: list[str]
    consent_granted: bool

    # IntakeAgent
    anamnesis_summary: str
    triage_score: str  # one of TRIAGE_LEVELS
    reply: str

    # routing: "IntakeAgent" | "ConsentAgent" | "SchedulingAgent" | "KIMAgent" | "END"
    next_agent: str

    # ConsentAgent
    iam_required: bool
    iam_message: str

    # SchedulingAgent
    appointment_id: Optional[str]
    slot_start: Optional[str]

    # KIMAgent
    letter: str
    kim_sent: bool
