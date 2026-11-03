from app.agents.consent_agent import consent_node


def test_without_consent_requests_iam_and_points_to_itself():
    r = consent_node({"consent_granted": False})
    assert r["iam_required"] is True
    assert r["iam_message"]
    assert r["next_agent"] == "ConsentAgent"


def test_missing_consent_flag_is_treated_as_denied():
    assert consent_node({})["iam_required"] is True


def test_with_consent_routes_to_scheduling():
    r = consent_node({"consent_granted": True})
    assert r["iam_required"] is False
    assert r["next_agent"] == "SchedulingAgent"
