# Agentic Patient Intake – gematik Accelerator

Agentic patient intake (anamnesis, triage, ePA consent, FHIR scheduling, KIM letter) built with FastAPI + LangGraph, with local mocks for the Telematikinfrastruktur (TI).

## Start

```powershell
Copy-Item .env.example .env
podman compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend (OpenAPI) | http://localhost:8000/docs |
| Mock ID-Dienst | http://localhost:8081/.well-known/openid-configuration |
| Mock KIS (HAPI FHIR) | http://localhost:8080/fhir |
| Mock KIM-CM (SMTP) | localhost:2525 |
| LLM (Ollama) | http://localhost:11434 (`podman compose exec llm ollama pull llama3.1`) |

Without a reachable LLM the intake agent uses a rule-based fallback.

## Agent flow

`intake_agent` → `consent_agent` → (consent granted) `scheduling_agent` → `kim_agent`.
Without ePA consent the flow ends after intake; no TI access is made.

## Login

The frontend signs in via OIDC authorization code flow with PKCE against the mock ID-Dienst
(demo patients `X110000001`, `X110000002`). The token lives in sessionStorage and the session
ends on expiry, logout or a 401 from the backend.

## Local frontend dev

```powershell
cd frontend
npm install
npm run dev      # dev server on http://localhost:3000
npm test         # Jest + Testing Library
npm run build    # production build
```

Config is read at build time: `REACT_APP_API_URL`, `REACT_APP_OIDC_ISSUER`, `REACT_APP_OIDC_CLIENT_ID`.
The container image builds the app and serves it with nginx (the values are passed as build args in `docker-compose.yml`).

## Backend API

All endpoints require the Gesundheits-ID bearer token. Conversation, triage and consent are kept
**server-side** per patient (in-memory store, `app/core/session.py`); the client cannot set them.

| Endpoint | Purpose |
|---|---|
| `POST /api/chat` `{message}` | Adds a patient message, runs the agent graph. Intake asks follow-up questions (LLM, rule-based fallback) until triage is set, then waits for consent. |
| `POST /api/consent` `{granted}` | Grant resumes the workflow: ePA medication plan → FHIR Appointment in the KIS → KIM letter. Idempotent after completion. `granted:false` revokes. |
| `DELETE /api/session` | Starts over / logout: drops conversation, triage and consent. |

Errors: `502` TI service (KIS/ePA) unreachable (retry is safe, nothing is double-booked), `409` intake
already completed or no active intake, `422` message too long, `429` rate limit. A failed KIM hand-over
does not fail the run; the response has `kim_sent: false`.
Every TI-relevant action (consent, ePA read, appointment, KIM) is written as a JSON line to the audit log
with a pseudonymised patient id and no medical content.

## Local backend dev

```powershell
cd backend
pip install -r requirements.txt
$env:AUTH_DISABLED="true"; uvicorn main:app --reload
```

## Persistence (PostgreSQL)

PostgreSQL is the only store (service postgres, volume pg-data; started with Podman via podman compose up --build). Schema is created on startup with create_all (no Alembic migrations yet).

| Table | Content |
|---|---|
| intake_session | conversation, triage score, summary, result (per patient sub; idle sessions are purged) |
| consent | durable consent records (scope, granted/expires/revoked, token jti); never deleted |
| udit | pseudonymised audit events (no medical content) |
| kim_outbox | Arztbrief + 	riage.json until delivered; retried every KIM_RETRY_INTERVAL_S; content wiped after sending |

Not persisted: access tokens, ePA medication data, slots/appointments (these stay in the KIS/ePA).

Limitations: the rate limiter is in memory per instance; a crash between the FHIR booking and the DB commit can leave a booking without session state. Tests use in-memory SQLite.

## Mock TI gateway (SMC-B / HSM-B)

All KIS and ePA calls of the backend go through `mock-ti-gateway` (port 8082): `FHIR_BASE_URL`/`EPA_BASE_URL` point to `http://mock-ti-gateway:8082/fhir`. The gateway keeps the patient's Gesundheits-ID token, adds `X-TI-Telematik-ID` and an RS256 assertion (`X-SMCB-Assertion`, certificate in `x5c`) signed with a simulated SMC-B key. The self-signed key is generated at start-up (or loaded from `certs/smcb_key.pem` + `smcb_cert.pem`) and is never committed. Follow it with `podman compose logs -f mock-ti-gateway`.

The HAPI mock does not verify the assertion; the signature check is covered by `backend/tests/test_ti_gateway.py`. In production the real gateway/Konnektor replaces this service and only the URLs change.
