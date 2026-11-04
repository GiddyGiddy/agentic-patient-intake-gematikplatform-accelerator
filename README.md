# Agentic Patient Intake – gematik Accelerator

Agentic patient intake for the gematik Telematikinfrastruktur (TI): structured anamnesis, Manchester triage, ePA consent, FHIR appointment booking in the KIS and a KIM letter to the referring doctor. Built with React, FastAPI, LangGraph, PostgreSQL and a local LLM. Runs **on-premise** with Podman; the TI services are simulated by local mocks for development and end-to-end tests.

## Current status

| Area | Status |
|---|---|
| Frontend (OIDC PKCE login, chat, consent dialog, emergency banner, result card, a11y) | Done, 26 Jest tests |
| Backend (agents, server-side session and consent, ePA read, FHIR booking, KIM, audit, hardening, ErrorHandler for TI failures) | Done, 66 pytest tests |
| PostgreSQL persistence (sessions, consent, audit, KIM outbox) | Done, tests pass on SQLite and on a real PostgreSQL; Alembic migrations for production |
| Mock TI services (ID-Dienst, KIS/ePA HAPI FHIR, KIM client module, TI gateway with simulated SMC-B) | Done |
| CI (GitHub Actions: tests on SQLite + PostgreSQL, frontend build, pip/npm audit, gitleaks, image builds + Trivy) | Done, green on GitHub |
| CD to the on-premise server (`cd.yml`, `compose.prod.yml`, `deploy/`) | Written; production image stack verified locally; not yet run on a real runner |
| Podman compose for the whole dev stack | Config validated; full `podman compose up --build` not yet run end-to-end |
| Browser run-through of frontend + backend + mocks together | Not yet done |
| Production TI connection (real gateway/Konnektor, SMC-B/HSM-B, real Gesundheits-ID) | Not part of this accelerator; only URLs/config change |

## Solution Architecture

![Agentic Patient Intake on-premise solution architecture](./docs/solution-architecture.svg)

The backend, database and LLM run in the clinic's own data center because the data is sensitive health data. Nothing is sent to a public cloud. The Azure items in the diagram (Arc, Monitor) are an optional management layer for operational metadata only. The icons are simplified drawings, not the official Azure icon set.

### Components

| Component | Technology | Where | Dev mock |
|---|---|---|---|
| Frontend | React 18, nginx | On-premise | – |
| Backend | FastAPI, LangGraph, SQLAlchemy | On-premise | – |
| Database | PostgreSQL 16 (only persistent store) | On-premise | – |
| LLM | Ollama (local, rule-based fallback) | On-premise | – |
| Gesundheits-ID (OIDC) | OpenID Connect / OAuth2 | TI | `mock-id-dienst` :8081 |
| TI gateway / Konnektor (HSM-B / SMC-B) | Reverse proxy, signs requests, adds Telematik-ID | TI | `mock-ti-gateway` :8082 |
| ePA + KIS (FHIR / ISiK) | HAPI FHIR | TI / clinic | `mock-kis-fhir` :8080 (+ `mock-kis-seed`) |
| KIM client module | SMTP | TI | `mock-kim-cm` :2525 |

## Start

```powershell
podman compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend (OpenAPI) | http://localhost:8000/docs |
| Mock ID-Dienst | http://localhost:8081/.well-known/openid-configuration |
| Mock TI gateway | http://localhost:8082/health |
| Mock KIS/ePA (HAPI FHIR) | http://localhost:8080/fhir |
| Mock KIM-CM (SMTP) | localhost:2525 |
| LLM (Ollama) | http://localhost:11434 (`podman compose exec llm ollama pull llama3.1`) |

Demo patients: `X110000001` (two active medications in the ePA), `X110000002` (none). Without a reachable LLM the intake agent uses a rule-based fallback. On Windows, use `127.0.0.1` instead of `localhost` for published database ports.

## Agent flow

```
POST /api/chat → intake_agent (anamnesis, Manchester triage)
      → consent_agent (stops until consent is granted)
      → scheduling_agent (FHIR Slot + Appointment in the KIS)
      → kim_agent (Arztbrief + triage.json → KIM outbox) → END
      scheduling failure (gateway/SMC-B error, timeout) → error_handler → END
```

- Consent, triage and conversation are held **server-side** per patient; the client cannot set them.
- The ePA medication plan is read only after consent, with the patient's Gesundheits-ID token.
- Red/orange patients get acute slots, green patients standard slots.
- KIS/gateway calls use a connect/read timeout (`FHIR_CONNECT_TIMEOUT_S`, `FHIR_READ_TIMEOUT_S`). Failures are mapped to `GATEWAY_TIMEOUT`, `GATEWAY_CONNECTION_FAILED`, `GATEWAY_AUTH_ERROR` or `GATEWAY_ERROR`; the `error_handler` node writes an alerting audit event (`scheduling_failed`), shows the patient a neutral German fallback message (no stack trace) and ends the run. The API response then has `scheduling_failed: true`.
- The graph is invoked in `backend/app/api/endpoints.py` (`_run`).

## Backend API

All endpoints require the Gesundheits-ID bearer token.

| Endpoint | Purpose |
|---|---|
| `POST /api/chat` `{message}` | Adds a patient message and runs the graph. Asks follow-up questions until triage is set, then waits for consent. |
| `POST /api/consent` `{granted}` | Grant resumes the workflow: ePA medication plan, FHIR Appointment, KIM letter. Idempotent after completion. `granted:false` revokes. |
| `DELETE /api/session` | Start over / logout: drops conversation, triage and consent. |
| `GET /health` | Status including database reachability (503 if the DB is down). |

Errors: `502` TI service (KIS/ePA) unreachable (retry is safe), `409` intake already completed or none active, `422` message too long, `429` rate limit. A failed KIM hand-over does not fail the run; the response has `kim_sent: false` and the outbox retries.

## Persistence (PostgreSQL)

PostgreSQL is the only store (service `postgres`, volume `pg-data`). In dev and tests the tables are created on startup (`DB_AUTO_CREATE=true`). In production the schema is owned by **Alembic** (`DB_AUTO_CREATE=false`); `deploy/deploy.sh` backs up the database and runs `alembic upgrade head` before the new backend starts.

```powershell
cd backend
alembic revision --autogenerate -m "describe change" # after changing app/core/db.py
alembic upgrade head                                 # uses DATABASE_URL
```

A database created earlier by `create_all` needs a one-time `alembic stamp 0001`. Keep migrations backward compatible (add before remove), because a rollback restores the previous images, not the schema.

| Table | Content |
|---|---|
| `intake_session` | conversation, triage score, summary, result (per patient `sub`; idle sessions are purged) |
| `consent` | durable consent records (scope, granted/expires/revoked, token `jti`); never deleted |
| `audit_event` | pseudonymised audit events (no medical content); also written as JSON lines |
| `kim_outbox` | Arztbrief + `triage.json` until delivered; retried every `KIM_RETRY_INTERVAL_S`; content wiped after sending |

Not persisted: access tokens, ePA medication data, slots and appointments (they stay in the KIS/ePA).

## Mock TI gateway (SMC-B / HSM-B)

All KIS and ePA calls go through `mock-ti-gateway`: `FHIR_BASE_URL` and `EPA_BASE_URL` point to `http://mock-ti-gateway:8082/fhir`. The gateway keeps the patient's token, adds `X-TI-Telematik-ID` and an RS256 assertion (`X-SMCB-Assertion`, certificate in `x5c`) signed with a simulated SMC-B key. The self-signed key is generated at start-up or loaded from `certs/smcb_key.pem` + `smcb_cert.pem`; it is never committed. Follow it with `podman compose logs -f mock-ti-gateway`. The HAPI mock does not verify the assertion; the signature is covered by `backend/tests/test_ti_gateway.py`.

## Security and privacy

- Token validation against the Gesundheits-ID JWKS; `AUTH_DISABLED` is for local development only.
- Audit log uses a pseudonymised patient id (sha256 prefix) and contains no medical content.
- CORS allow-list, message length cap and per-patient rate limit.
- Consent is revoked on reset or session timeout.

## Development

```powershell
# backend
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                                   # in-memory SQLite
$env:TEST_DATABASE_URL="postgresql+psycopg://intake:intake@127.0.0.1:55432/intake"; python -m pytest -q   # real PostgreSQL
$env:AUTH_DISABLED="true"; uvicorn main:app --reload

# frontend
cd frontend
npm install
npm run dev      # http://localhost:3000
npm test         # Jest + Testing Library
npm run build
```

Frontend config is read at build time: `REACT_APP_API_URL`, `REACT_APP_OIDC_ISSUER`, `REACT_APP_OIDC_CLIENT_ID` (passed as build args in `docker-compose.yml`). See `.env` for all backend settings.

## CI/CD (on-premise production)

| Piece | Purpose |
|---|---|
| `.github/workflows/ci.yml` | On every PR and push to `main`: backend tests (SQLite + PostgreSQL), frontend tests and build, `pip-audit`, `npm audit` (critical), gitleaks, compose validation, image builds with Trivy (fixable HIGH/CRITICAL fail). |
| `.github/workflows/cd.yml` | After CI succeeds on `main`: build images tagged with the commit SHA, push to the on-prem registry, SBOM, cosign signature, deploy to staging with smoke tests, then to production after manual approval. Skipped until the repository variable `REGISTRY` is set. |
| `compose.prod.yml` | Production stack from registry images only: TLS proxy, frontend, backend, PostgreSQL, local LLM. No mocks, no published backend/DB ports, internal network without internet access. |
| `deploy/deploy.sh` | Pull, `pg_dump`, `alembic upgrade head`, `up -d`, health wait, **automatic rollback** to the previous tag. |
| `deploy/smoke-test.sh` | Black-box checks: health, frontend, HTTPS redirect, HSTS, auth enforced on the API. |
| `deploy/prod.env.example` | Template for the server-side secrets file `/etc/intake/<env>.env` (never committed). |

To enable deployments: register a self-hosted runner on the server (labels `onprem`, `staging`, `production`), set the repository variables (`REGISTRY`, `STAGING_URL`, `PROD_URL`, `PROD_API_URL`, `PROD_OIDC_ISSUER`, `PROD_OIDC_CLIENT_ID`, `COSIGN_PUBLIC_KEY`) and secrets (`REGISTRY_USER`, `REGISTRY_PASSWORD`, `COSIGN_PRIVATE_KEY`, `COSIGN_PASSWORD`), create the `staging` and `production` environments (required reviewers on production), and place the TLS certificate (`fullchain.pem`, `privkey.pem`) and SMC-B certificate on the server. Redeploy or roll back by running the CD workflow manually with an existing image tag.

## Known limitations

- Full dev stack not yet exercised end-to-end in containers or a browser.
- The CD pipeline has not run on a real self-hosted runner yet.
- A rollback does not revert the database schema (restore the `pg_dump` manually if needed).
- The `error_handler` alert is an audit-log entry; there is no Sentry/Prometheus hook yet.
- Rate limiter is in memory per instance.
- A crash between the FHIR booking and the DB commit can leave a booking without session state.
- Consent is not yet tied to a fresh Gesundheits-ID authentication.
- The HAPI mock does not verify the SMC-B assertion.
- Production needs a real TI gateway/Konnektor, SMC-B/HSM-B and gematik-approved IdP.
