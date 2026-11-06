# Deployment setup (pull-based CD with GHCR)

Flow: a merge to `main` passes CI, then `cd.yml` builds the images on GitHub-hosted runners, scans them
with Trivy and pushes them to GHCR as `ghcr.io/<owner>/intake/{backend,frontend,mock-ti-gateway}:<12-char-sha>`.
The server pulls and deploys by running `deploy/deploy.sh` (pull, DB backup, Alembic, start, health check,
automatic rollback). No runner or inbound access to the server is needed.

## 1. GitHub

Optional repository variables (Settings > Secrets and variables > Actions > Variables):

| Name | Purpose |
|---|---|
| `PROD_API_URL`, `PROD_OIDC_ISSUER`, `PROD_OIDC_CLIENT_ID` | baked into the frontend image (the frontend is configured at build time) |
| `REGISTRY` | only to override the default `ghcr.io/<owner>/intake` |

Optional secrets for signing: `COSIGN_PRIVATE_KEY`, `COSIGN_PASSWORD` (images are signed only if the key exists).

Then run Actions > CD > Run workflow on `main` (or merge to `main`). The run summary shows the tag.

## 2. Server (Ubuntu)

```bash
sudo apt update && sudo apt -y install podman curl git docker-compose-v2 openssl
sudo adduser --disabled-password --gecos "" runner && sudo loginctl enable-linger runner
sudo -iu runner
git clone https://github.com/GiddyGiddy/agentic-patient-intake-gematikplatform-accelerator.git app
cd app && exit
sudo ./app/deploy/setup-server.sh staging runner      # run from the repo as root
sudo nano /etc/intake/staging.env                     # replace CHANGE_ME values
```

TLS certificate (self-signed is fine for staging; production needs one from the internal CA):

```bash
sudo openssl req -x509 -newkey rsa:4096 -nodes -days 365 \
  -keyout /etc/intake/tls/privkey.pem -out /etc/intake/tls/fullchain.pem -subj "/CN=<vm-ip-or-hostname>"
sudo chown runner /etc/intake/tls/*
```

## 3. Let the server pull from GHCR

GHCR packages are private by default. Create a GitHub personal access token (classic) with only `read:packages`:

```bash
sudo -iu runner
echo "<token>" | podman login ghcr.io -u <github-user> --password-stdin
```

(Alternatively make the three packages public in GitHub > Packages; the images contain no patient data.)

## 4. Deploy

```bash
sudo -iu runner
cd app && git pull
export REGISTRY=ghcr.io/<owner-lowercase>/intake
./deploy/deploy.sh staging <12-char-sha>
./deploy/smoke-test.sh https://<vm-ip-or-hostname>
```

`deploy.sh` rolls back to the previous tag if the new one does not become healthy. The first deploy has no
previous tag, so a failure leaves the stack down; check `podman compose -p intake-staging -f compose.prod.yml logs`.
Roll back or redeploy any time by running `deploy.sh` with an older tag. Use `production` and
`/etc/intake/production.env` on the production host.

## Later: self-hosted runner and signed approvals

If you later want automatic deploys with an approval gate, add a self-hosted runner with deploy jobs
(environments `staging` / `production` with required reviewers) and verify signatures with `cosign verify`
before `deploy.sh`. Not required for the pull-based flow.
