from datetime import datetime, timedelta, timezone

from fhirpy import SyncFHIRClient

from app.agents.state import IntakeState
from config import settings

# Earliest acceptable start per Manchester level: Rot/Orange/Gelb get acute slots, Grün/Blau standard ones
_EARLIEST = {
    "Rot": timedelta(0),
    "Orange": timedelta(minutes=10),
    "Gelb": timedelta(hours=1),
    "Grün": timedelta(days=2),
    "Blau": timedelta(days=7),
}


def _find_free_slot(client: SyncFHIRClient, earliest: datetime):
    try:
        slots = (
            client.resources("Slot")
            .search(status="free", start__ge=earliest.isoformat())
            .sort("start")
            .limit(1)
            .fetch()
        )
        return slots[0] if slots else None
    except Exception:
        return None


def scheduling_node(state: IntakeState) -> IntakeState:
    client = SyncFHIRClient(settings.fhir_base_url)
    score = state.get("triage_score", "Grün")
    earliest = datetime.now(timezone.utc) + _EARLIEST.get(score, timedelta(days=2))

    slot = _find_free_slot(client, earliest)
    if slot is not None:
        start, end = slot["start"], slot["end"]
        slot_ref = {"reference": f"Slot/{slot.id}"}
    else:
        # no free slot published by the KIS: request the earliest allowed time
        start_dt = earliest.replace(second=0, microsecond=0)
        start, end = start_dt.isoformat(), (start_dt + timedelta(minutes=20)).isoformat()
        slot_ref = None

    data = {
        "status": "booked" if slot_ref else "proposed",
        "priority": 1 if score in ("Rot", "Orange") else 5,
        "description": state.get("anamnesis_summary", "")[:200],
        "start": start,
        "end": end,
        "participant": [
            {"actor": {"display": f"Patient {state['patient_id']}"}, "status": "accepted"}
        ],
    }
    if slot_ref:
        data["slot"] = [slot_ref]
    appt = client.resource("Appointment", **data)
    appt.save()

    if slot_ref:
        slot["status"] = "busy"
        slot.save()

    return {"appointment_id": appt.id, "slot_start": start, "next_agent": "KIMAgent"}
