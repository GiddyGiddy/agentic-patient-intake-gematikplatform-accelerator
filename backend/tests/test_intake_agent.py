import pytest

from app.agents import intake_agent
from app.agents.intake_agent import intake_node


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ich habe starke Brustschmerzen", "Rot"),
        ("starke Schmerzen im Bein", "Orange"),
        ("Fieber seit gestern", "Gelb"),
        ("Husten", "Grün"),
        ("Ich brauche ein Rezept", "Blau"),
    ],
)
def test_keyword_score(text, expected):
    assert intake_agent._keyword_score(text) == expected


def test_red_triggers_immediately_and_routes_to_consent():
    r = intake_node({"messages": ["Ich habe Brustschmerzen"]})
    assert r["triage_score"] == "Rot"
    assert r["next_agent"] == "ConsentAgent"
    assert "112" in r["reply"]


def test_non_red_asks_followup_until_enough_info():
    r = intake_node({"messages": ["Husten"]})
    assert "triage_score" not in r
    assert r["next_agent"] == "END"


def test_non_red_completes_after_enough_messages():
    r = intake_node({"messages": ["Husten", "seit drei Tagen"]})
    assert r["triage_score"] == "Grün"
    assert r["anamnesis_summary"]
    assert r["next_agent"] == "ConsentAgent"


def test_llm_can_raise_but_not_lower_urgency(monkeypatch):
    monkeypatch.setattr(
        intake_agent, "_llm_assess", lambda t: {"summary": "s", "triage_score": "Orange"}
    )
    assert intake_node({"messages": ["Husten", "stark"]})["triage_score"] == "Orange"

    monkeypatch.setattr(
        intake_agent, "_llm_assess", lambda t: {"summary": "s", "triage_score": "Blau"}
    )
    assert intake_node({"messages": ["Brustschmerzen"]})["triage_score"] == "Rot"


def test_llm_failure_falls_back_to_keywords(monkeypatch):
    monkeypatch.setattr(intake_agent, "_llm_assess", lambda t: None)
    r = intake_node({"messages": ["Fieber", "seit 2 Tagen"]})
    assert r["triage_score"] == "Gelb"
