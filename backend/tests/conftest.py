import pytest

from config import settings


@pytest.fixture(autouse=True)
def no_llm_no_auth(monkeypatch):
    """Tests never call a real LLM and skip token validation."""
    monkeypatch.setattr(settings, "llm_base_url", "")
    monkeypatch.setattr(settings, "auth_disabled", True)
    monkeypatch.setattr(
        "app.agents.consent_agent.fetch_medication_plan", lambda *a: (["Ramipril 5 mg"], True)
    )
