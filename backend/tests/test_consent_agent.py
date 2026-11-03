from app.agents import consent_agent
from app.agents.consent_agent import consent_node


def test_without_consent_requests_iam_and_points_to_itself(monkeypatch):
    called = []
    monkeypatch.setattr(consent_agent, "fetch_medication_plan", lambda *a: called.append(1) or ([], True))
    r = consent_node({"consent_granted": False})
    assert r["iam_required"] is True
    assert r["iam_message"]
    assert r["next_agent"] == "ConsentAgent"
    assert called == []  # no ePA access without consent


def test_missing_consent_flag_is_treated_as_denied():
    assert consent_node({})["iam_required"] is True


def test_with_consent_reads_epa_with_token_and_routes_to_scheduling(monkeypatch):
    seen = {}

    def fake(pid, token):
        seen.update(pid=pid, token=token)
        return ["Ramipril 5 mg"], True

    monkeypatch.setattr(consent_agent, "fetch_medication_plan", fake)
    r = consent_node({"consent_granted": True, "patient_id": "X1", "access_token": "tok"})
    assert r["iam_required"] is False
    assert r["next_agent"] == "SchedulingAgent"
    assert r["medication_plan"] == ["Ramipril 5 mg"]
    assert r["epa_available"] is True
    assert seen == {"pid": "X1", "token": "tok"}
