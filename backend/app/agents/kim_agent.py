import json

import httpx

from app.agents.state import IntakeState
from app.core.kim_client import send_kim_message
from config import settings


def _meds_text(state: IntakeState) -> str:
    meds = state.get("medication_plan") or []
    if meds:
        return "Medikationsplan (ePA): " + "; ".join(meds)
    if state.get("epa_available") is False:
        return "Medikationsplan: ePA nicht erreichbar."
    return "Medikationsplan (ePA): keine aktiven Eintraege."


def _template_letter(state: IntakeState) -> str:
    return (
        "Sehr geehrte Kollegin, sehr geehrter Kollege,\n\n"
        "wir übersenden Ihnen die Aufnahmeinformationen zu Ihrem Patienten "
        f"(ID {state['patient_id']}). Die Ersteinschätzung nach dem Manchester-Triage-System "
        f"ergab die Dringlichkeit {state.get('triage_score')}.\n\n"
        f"Anamnese: {state.get('anamnesis_summary', '')}\n\n"
        f"{_meds_text(state)}\n\n"
        f"Termin: {state.get('slot_start')} (Appointment/{state.get('appointment_id')}).\n\n"
        "Mit freundlichen kollegialen Grüßen"
    )


def _llm_letter(state: IntakeState) -> str | None:
    if not settings.llm_base_url:
        return None
    prompt = (
        "Schreibe einen formellen medizinischen Arztbrief als Fließtext auf Deutsch "
        "(Anrede, Anamnese, Einschätzung, Termin, Grußformel). Erfinde keine Befunde.\n"
        f"Anamnese: {state.get('anamnesis_summary')}\n"
        f"Triage (Manchester): {state.get('triage_score')}\n"
        f"{_meds_text(state)}\n"
        f"Termin: {state.get('slot_start')}"
    )
    try:
        r = httpx.post(
            f"{settings.llm_base_url}/api/generate",
            json={"model": settings.llm_model, "stream": False, "prompt": prompt},
            timeout=120,
        )
        r.raise_for_status()
        return r.json().get("response") or None
    except httpx.HTTPError:
        return None


def kim_node(state: IntakeState) -> IntakeState:
    letter = _llm_letter(state) or _template_letter(state)
    triage_record = {
        "patient_id": state["patient_id"],
        "triage_system": "Manchester",
        "triage_score": state.get("triage_score"),
        "appointment_id": state.get("appointment_id"),
        "slot_start": state.get("slot_start"),
        "medication_plan": state.get("medication_plan", []),
    }
    send_kim_message(
        "Arztbrief - Patientenaufnahme",
        letter,
        attachments=[("triage.json", json.dumps(triage_record, ensure_ascii=False).encode())],
    )
    return {"letter": letter, "kim_sent": True, "next_agent": "END"}
