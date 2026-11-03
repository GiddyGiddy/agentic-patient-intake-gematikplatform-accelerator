import httpx

from config import settings


def _describe(statement: dict) -> str | None:
    concept = statement.get("medicationCodeableConcept") or {}
    name = concept.get("text") or next(
        (c.get("display") for c in concept.get("coding", []) if c.get("display")), None
    )
    if not name:
        name = (statement.get("medicationReference") or {}).get("display")
    if not name:
        return None
    dosage = next((d.get("text") for d in statement.get("dosage", []) if d.get("text")), None)
    return f"{name} ({dosage})" if dosage else name


def fetch_medication_plan(patient_id: str, access_token: str | None) -> tuple[list[str], bool]:
    """Reads the medication plan (FHIR MedicationStatement) of the patient from the ePA.

    The patient's Gesundheits-ID access token is forwarded. In dev the call goes to the HAPI mock,
    in production to the TI gateway/Konnektor, which handles TLS and SMC-B. The FHIR API is the same.
    Returns (medications, reachable); an unreachable ePA must not break the intake.
    """
    headers = {"Accept": "application/fhir+json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    try:
        r = httpx.get(
            f"{settings.epa_base_url}/MedicationStatement",
            params={"subject": f"Patient/{patient_id}", "status": "active", "_count": 100},
            headers=headers,
            timeout=settings.epa_timeout_s,
        )
        r.raise_for_status()
        entries = r.json().get("entry", [])
    except (httpx.HTTPError, ValueError):
        return [], False
    meds = [m for e in entries if (m := _describe(e.get("resource", {})))]
    return meds, True
