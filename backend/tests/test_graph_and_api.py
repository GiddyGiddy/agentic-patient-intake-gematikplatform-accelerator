import pytest
from fastapi.testclient import TestClient
from langgraph.graph import END

import app.agents.graph as graph_mod
from app.agents.graph import route_next_step
from config import settings
from main import app


def test_route_next_step_maps_agents():
    assert route_next_step({"next_agent": "SchedulingAgent"}) == "scheduling"
    assert route_next_step({"next_agent": "KIMAgent"}) == "kim"
    assert route_next_step({"next_agent": "END"}) == END
    assert route_next_step({}) == END


def test_pending_iam_stops_the_run():
    assert route_next_step({"next_agent": "ConsentAgent", "iam_required": True}) == END


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def stub_ti(monkeypatch):
    """Replaces scheduling/KIM so the full graph runs without TI services."""
    calls = []
    monkeypatch.setattr(
        graph_mod,
        "scheduling_node",
        lambda s: calls.append("scheduling")
        or {"appointment_id": "a1", "slot_start": "t", "next_agent": "KIMAgent"},
    )
    monkeypatch.setattr(
        graph_mod, "kim_node", lambda s: calls.append("kim") or {"kim_sent": True, "next_agent": "END"}
    )
    monkeypatch.setattr("app.api.endpoints.intake_graph", graph_mod.build_graph())
    return calls


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_chat_without_consent_stops_at_consent_agent(client, stub_ti):
    body = client.post("/api/chat", json={"message": "Ich habe starke Brustschmerzen"}).json()
    assert body["triage_score"] == "Rot"
    assert body["iam_required"] is True
    assert body["kim_sent"] is False
    assert stub_ti == []


def test_chat_resumes_after_consent_through_scheduling_and_kim(client, stub_ti):
    first = client.post("/api/chat", json={"message": "Ich habe starke Brustschmerzen"}).json()
    body = client.post(
        "/api/chat",
        json={
            "message": "Ich habe starke Brustschmerzen",
            "consent_granted": True,
            "triage_score": first["triage_score"],
            "anamnesis_summary": first["anamnesis_summary"],
        },
    ).json()
    assert stub_ti == ["scheduling", "kim"]
    assert body["appointment_id"] == "a1"
    assert body["kim_sent"] is True
    assert body["iam_required"] is False


def test_chat_requires_token_when_auth_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401
