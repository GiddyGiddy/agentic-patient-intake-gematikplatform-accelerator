from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from langgraph.graph import END

import app.agents.graph as graph_mod
from app.agents.graph import route_next_step
from app.core.db import ConsentRow, IntakeSessionRow, db_session, utcnow
from app.core.session import store
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


def _chat(client, msg):
    return client.post("/api/chat", json={"message": msg})


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": True}


def test_chat_without_consent_stops_and_keeps_state_server_side(client, stub_ti):
    body = _chat(client, "Ich habe starke Brustschmerzen").json()
    assert body["triage_score"] == "Rot"
    assert body["iam_required"] is True
    assert body["consent_granted"] is False
    assert body["kim_sent"] is False
    assert stub_ti == []


def test_client_cannot_inject_consent_or_triage(client, stub_ti):
    body = client.post(
        "/api/chat",
        json={"message": "Husten", "consent_granted": True, "triage_score": "Rot"},
    ).json()
    assert body["consent_granted"] is False
    assert body["triage_score"] is None
    assert stub_ti == []


def test_consent_grant_resumes_through_epa_scheduling_and_kim(client, stub_ti):
    _chat(client, "Ich habe starke Brustschmerzen")
    body = client.post("/api/consent", json={"granted": True}).json()
    assert stub_ti == ["scheduling", "kim"]
    assert body["appointment_id"] == "a1"
    assert body["kim_sent"] is True
    assert body["iam_required"] is False
    assert body["consent_granted"] is True
    assert body["medication_plan"] == ["Ramipril 5 mg"]
    assert body["epa_available"] is True


def test_consent_grant_is_idempotent_after_completion(client, stub_ti):
    _chat(client, "Brustschmerzen")
    client.post("/api/consent", json={"granted": True})
    again = client.post("/api/consent", json={"granted": True}).json()
    assert again["appointment_id"] == "a1"
    assert stub_ti == ["scheduling", "kim"]  # not booked twice


def test_consent_without_intake_is_rejected(client, stub_ti):
    assert client.post("/api/consent", json={"granted": True}).status_code == 409


def test_pending_consent_does_not_rerun_intake(client, stub_ti):
    first = _chat(client, "Brustschmerzen").json()
    again = _chat(client, "noch eine Nachricht").json()
    assert again["triage_score"] == first["triage_score"]
    assert again["iam_required"] is True


def test_revoked_consent_blocks_further_ti_access(client, stub_ti):
    _chat(client, "Husten")  # follow-up question, intake not finished
    body = client.post("/api/consent", json={"granted": False}).json()
    assert body["consent_granted"] is False


def test_chat_after_completion_is_rejected(client, stub_ti):
    _chat(client, "Brustschmerzen")
    client.post("/api/consent", json={"granted": True})
    assert _chat(client, "nochmal").status_code == 409


def test_reset_session_starts_over(client, stub_ti):
    _chat(client, "Brustschmerzen")
    assert client.delete("/api/session").status_code == 204
    body = _chat(client, "Husten").json()
    assert body["triage_score"] is None


def test_ti_failure_returns_502_and_allows_retry(client, monkeypatch):
    def boom(state):
        raise ConnectionError("kis down")

    monkeypatch.setattr(graph_mod, "scheduling_node", boom)
    monkeypatch.setattr("app.api.endpoints.intake_graph", graph_mod.build_graph())
    _chat(client, "Brustschmerzen")
    assert client.post("/api/consent", json={"granted": True}).status_code == 502

    monkeypatch.setattr(
        graph_mod, "scheduling_node", lambda s: {"appointment_id": "a2", "slot_start": "t", "next_agent": "KIMAgent"}
    )
    monkeypatch.setattr(
        graph_mod, "kim_node", lambda s: {"kim_sent": True, "next_agent": "END"}
    )
    monkeypatch.setattr("app.api.endpoints.intake_graph", graph_mod.build_graph())
    assert client.post("/api/consent", json={"granted": True}).json()["appointment_id"] == "a2"


def test_message_length_and_rate_limit(client, stub_ti, monkeypatch):
    assert _chat(client, "x" * (settings.max_message_chars + 1)).status_code == 422
    monkeypatch.setattr(settings, "rate_limit_per_min", 2)
    assert _chat(client, "a").status_code == 200
    assert _chat(client, "b").status_code == 200
    assert _chat(client, "c").status_code == 429


def test_chat_requires_token_when_auth_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    assert _chat(client, "hi").status_code == 401
    assert client.post("/api/consent", json={"granted": True}).status_code == 401
    assert client.delete("/api/session").status_code == 401


def test_consent_expires(client, stub_ti, monkeypatch):
    _chat(client, "Brustschmerzen")
    client.post("/api/consent", json={"granted": True})
    with db_session() as s:  # pretend the booking did not finish and the consent is long expired
        s.get(IntakeSessionRow, "dev-patient").result = {}
        for row in s.query(ConsentRow):
            row.expires_at = utcnow() - timedelta(hours=1)
    body = _chat(client, "und noch").json()
    assert body["iam_required"] is True


