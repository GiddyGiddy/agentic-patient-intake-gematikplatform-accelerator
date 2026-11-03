from datetime import datetime, timedelta, timezone

import pytest

from app.agents import scheduling_agent
from app.agents.scheduling_agent import scheduling_node


class FakeResource(dict):
    saved = False

    def __init__(self, id=None, **data):
        super().__init__(**data)
        self.id = id

    def save(self):
        self.saved = True
        self.id = self.id or "appt-1"


class FakeSearch:
    def __init__(self, slots):
        self.slots = slots

    def search(self, **kw):
        return self

    def sort(self, *a):
        return self

    def limit(self, *a):
        return self

    def fetch(self):
        return self.slots


class FakeClient:
    def __init__(self, slots):
        self.slots = slots
        self.created = []

    def resources(self, name):
        return FakeSearch(self.slots)

    def resource(self, name, **data):
        r = FakeResource(**data)
        self.created.append(r)
        return r


def _use(monkeypatch, slots):
    client = FakeClient(slots)
    monkeypatch.setattr(scheduling_agent, "SyncFHIRClient", lambda url: client)
    return client


def test_books_free_slot_and_marks_it_busy(monkeypatch):
    slot = FakeResource(id="s1", start="2030-01-01T10:00:00Z", end="2030-01-01T10:20:00Z", status="free")
    client = _use(monkeypatch, [slot])

    r = scheduling_node({"patient_id": "p1", "triage_score": "Gelb", "anamnesis_summary": "x"})

    appt = client.created[0]
    assert appt["status"] == "booked"
    assert appt["slot"] == [{"reference": "Slot/s1"}]
    assert appt["start"] == slot["start"]
    assert slot["status"] == "busy" and slot.saved
    assert r == {"appointment_id": "appt-1", "slot_start": slot["start"], "next_agent": "KIMAgent"}


def test_without_free_slot_proposes_appointment(monkeypatch):
    client = _use(monkeypatch, [])
    scheduling_node({"patient_id": "p1", "triage_score": "Grün"})
    appt = client.created[0]
    assert appt["status"] == "proposed"
    assert "slot" not in appt


@pytest.mark.parametrize(
    "score,priority,min_delay",
    [
        ("Rot", 1, timedelta(0)),
        ("Orange", 1, timedelta(minutes=9)),
        ("Gelb", 5, timedelta(minutes=59)),
        ("Grün", 5, timedelta(days=1, hours=23)),
        ("Blau", 5, timedelta(days=6, hours=23)),
    ],
)
def test_acuity_drives_priority_and_earliest_start(monkeypatch, score, priority, min_delay):
    client = _use(monkeypatch, [])
    scheduling_node({"patient_id": "p1", "triage_score": score})
    appt = client.created[0]
    assert appt["priority"] == priority
    start = datetime.fromisoformat(appt["start"])
    assert start >= datetime.now(timezone.utc) + min_delay - timedelta(minutes=1)


def test_acute_slot_is_earlier_than_standard(monkeypatch):
    client = _use(monkeypatch, [])
    scheduling_node({"patient_id": "p", "triage_score": "Gelb"})
    scheduling_node({"patient_id": "p", "triage_score": "Grün"})
    gelb, gruen = (datetime.fromisoformat(a["start"]) for a in client.created)
    assert gelb < gruen
