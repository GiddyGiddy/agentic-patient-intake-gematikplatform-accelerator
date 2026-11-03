# Agentic Patient Intake – gematik Accelerator

Agentic patient intake (anamnesis, triage, ePA consent, FHIR scheduling, KIM letter) built with FastAPI + LangGraph, with local mocks for the Telematikinfrastruktur (TI).

## Start

```powershell
Copy-Item .env.example .env
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend (OpenAPI) | http://localhost:8000/docs |
| Mock ID-Dienst | http://localhost:8081/.well-known/openid-configuration |
| Mock KIS (HAPI FHIR) | http://localhost:8080/fhir |
| Mock KIM-CM (SMTP) | localhost:2525 |
| LLM (Ollama) | http://localhost:11434 (`docker compose exec llm ollama pull llama3.1`) |

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
The Docker image builds the app and serves it with nginx (the values are passed as build args in `docker-compose.yml`).

## Local backend dev

```powershell
cd backend
pip install -r requirements.txt
$env:AUTH_DISABLED="true"; uvicorn main:app --reload
```
