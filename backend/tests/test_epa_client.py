import httpx
import pytest

from app.core import epa_client
from config import settings


def _bundle(*statements):
    return {"entry": [{"resource": s} for s in statements]}


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_reads_medication_plan_with_patient_token(monkeypatch):
    seen = {}

    def fake_get(url, params, headers, timeout):
        seen.update(url=url, params=params, headers=headers)
        return _Resp(
            _bundle(
                {"medicationCodeableConcept": {"text": "Ramipril 5 mg"}, "dosage": [{"text": "1-0-0"}]},
                {"medicationCodeableConcept": {"coding": [{"display": "Metformin"}]}},
                {"status": "active"},  # no medication name -> skipped
            )
        )

    monkeypatch.setattr(epa_client.httpx, "get", fake_get)
    meds, reachable = epa_client.fetch_medication_plan("X1", "tok")

    assert meds == ["Ramipril 5 mg (1-0-0)", "Metformin"]
    assert reachable is True
    assert seen["url"] == f"{settings.epa_base_url}/MedicationStatement"
    assert seen["params"]["subject"] == "Patient/X1"
    assert seen["headers"]["Authorization"] == "Bearer tok"


def test_unreachable_epa_is_reported_not_raised(monkeypatch):
    def boom(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(epa_client.httpx, "get", boom)
    assert epa_client.fetch_medication_plan("X1", "tok") == ([], False)


def test_empty_plan_is_reachable(monkeypatch):
    monkeypatch.setattr(epa_client.httpx, "get", lambda *a, **k: _Resp({}))
    assert epa_client.fetch_medication_plan("X1", None) == ([], True)
