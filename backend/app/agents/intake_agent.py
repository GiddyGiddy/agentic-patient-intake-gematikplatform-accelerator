import json

import httpx

from app.agents.state import TRIAGE_LEVELS, IntakeState
from config import settings

RED = ("brustschmerz", "atemnot", "bewusstlos", "lähmung", "krampfanfall", "chest pain", "unconscious")
ORANGE = ("starke schmerzen", "blutung", "severe pain", "bleeding")
YELLOW = ("fieber", "erbrechen", "fever", "vomiting")
GREEN = ("schmerz", "husten", "pain", "cough")

MIN_PATIENT_MESSAGES = 2  # non-red cases need at least this many answers before triage
MAX_PATIENT_MESSAGES = 6  # stop asking follow-up questions after this many answers
FALLBACK_QUESTION = "Danke. Seit wann bestehen die Beschwerden und wie stark sind sie?"


def _keyword_score(text: str) -> str:
    t = text.lower()
    for level, words in (("Rot", RED), ("Orange", ORANGE), ("Gelb", YELLOW), ("Grün", GREEN)):
        if any(w in t for w in words):
            return level
    return "Blau"


def _more_urgent(a: str, b: str) -> str:
    return min(a, b, key=TRIAGE_LEVELS.index)


def _llm_assess(text: str) -> dict | None:
    if not settings.llm_base_url:
        return None
    prompt = (
        "Du bist ein medizinischer Anamnese-Assistent. Fasse die Angaben des Patienten "
        "als Anamnese zusammen und vergib eine Dringlichkeit nach dem Manchester-Triage-System "
        '(Rot, Orange, Gelb, Grün, Blau). Antworte nur als JSON: '
        '{"summary": "...", "triage_score": "..."}\n\nPatientenangaben:\n' + text
    )
    try:
        r = httpx.post(
            f"{settings.llm_base_url}/api/generate",
            json={"model": settings.llm_model, "stream": False, "format": "json", "prompt": prompt},
            timeout=120,
        )
        r.raise_for_status()
        data = json.loads(r.json()["response"])
        if data.get("triage_score") in TRIAGE_LEVELS and data.get("summary"):
            return data
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return None


def _llm_followup(text: str) -> str | None:
    """Returns the next anamnesis question, or None if the LLM considers the anamnesis complete/unavailable."""
    if not settings.llm_base_url:
        return None
    prompt = (
        "Du fuehrst eine strukturierte Anamnese (Beschwerden, Beginn, Staerke, Vorerkrankungen, "
        "Medikamente). Entscheide anhand der bisherigen Patientenangaben, ob noch eine wichtige "
        "Information fehlt. Antworte nur als JSON: "
        '{"complete": true|false, "question": "eine kurze Frage auf Deutsch"}\n\nPatientenangaben:\n'
        + text
    )
    try:
        r = httpx.post(
            f"{settings.llm_base_url}/api/generate",
            json={"model": settings.llm_model, "stream": False, "format": "json", "prompt": prompt},
            timeout=60,
        )
        r.raise_for_status()
        data = json.loads(r.json()["response"])
        question = data.get("question")
        if data.get("complete") is False and isinstance(question, str) and question.strip():
            return question.strip()
    except (httpx.HTTPError, ValueError, KeyError, AttributeError):
        pass
    return None


def intake_node(state: IntakeState) -> IntakeState:
    messages = state.get("messages", [])
    text = " ".join(messages)
    keyword = _keyword_score(text)

    if keyword != "Rot":
        question = None
        if len(messages) < MIN_PATIENT_MESSAGES:
            question = _llm_followup(text) or FALLBACK_QUESTION
        elif len(messages) < MAX_PATIENT_MESSAGES:
            question = _llm_followup(text)
        if question:
            return {"reply": question, "next_agent": "END"}
    llm = _llm_assess(text)
    # the LLM may raise but never lower what the safety keywords flagged
    score = _more_urgent(keyword, llm["triage_score"]) if llm else keyword
    summary = llm["summary"] if llm else f"Patientenangaben: {text}"

    reply = (
        "Ihre Beschwerden sind möglicherweise lebensbedrohlich. Bitte rufen Sie sofort den Notruf 112."
        if score == "Rot"
        else f"Danke, die Anamnese ist vollständig (Dringlichkeit: {score})."
    )
    return {
        "anamnesis_summary": summary,
        "triage_score": score,
        "reply": reply,
        "next_agent": "ConsentAgent",
    }
