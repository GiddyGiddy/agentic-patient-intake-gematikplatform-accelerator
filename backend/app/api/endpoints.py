from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.graph import intake_graph
from app.core.security import get_current_user

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[str] = []
    consent_granted: bool = False
    # returned by the first call; sent back after the IAM approval to resume the workflow
    triage_score: str | None = None
    anamnesis_summary: str | None = None


@router.post("/chat")
def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    """Runs one pass of the agent graph for the authenticated patient."""
    state = {
        "patient_id": user["sub"],
        "messages": [*req.history, req.message],
        "consent_granted": req.consent_granted,
    }
    if req.triage_score:
        state["triage_score"] = req.triage_score
        state["anamnesis_summary"] = req.anamnesis_summary or ""
    result = intake_graph.invoke(state)
    return {
        "reply": result.get("reply"),
        "triage_score": result.get("triage_score") or req.triage_score,
        "anamnesis_summary": result.get("anamnesis_summary") or req.anamnesis_summary,
        "iam_required": result.get("iam_required", False),
        "iam_message": result.get("iam_message"),
        "appointment_id": result.get("appointment_id"),
        "kim_sent": result.get("kim_sent", False),
    }
