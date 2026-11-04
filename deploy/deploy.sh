#!/usr/bin/env bash
# Usage: deploy/deploy.sh <staging|production> <image-tag>
# Pulls the tag, backs up PostgreSQL, starts the stack, waits for health and rolls back to
# the previously deployed tag if the new one does not become healthy.
set -euo pipefail

ENVIRONMENT="${1:?environment (staging|production)}"
TAG="${2:?image tag}"

: "${REGISTRY:?REGISTRY must be set, e.g. registry.klinik.local/intake}"
STATE_DIR="${STATE_DIR:-/var/lib/intake}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/intake}"
export PROD_ENV_FILE="${PROD_ENV_FILE:-/etc/intake/${ENVIRONMENT}.env}"
export REGISTRY BACKUP_DIR
PROJECT="intake-${ENVIRONMENT}"
HEALTH_URL="${HEALTH_URL:-https://127.0.0.1/health}"
HEALTH_TIMEOUT_S="${HEALTH_TIMEOUT_S:-120}"
KEEP_BACKUPS="${KEEP_BACKUPS:-14}"

if command -v podman >/dev/null 2>&1; then ENGINE=podman; else ENGINE=docker; fi
compose() { "$ENGINE" compose -p "$PROJECT" -f compose.prod.yml "$@"; }

[ -r "$PROD_ENV_FILE" ] || { echo "missing env file $PROD_ENV_FILE" >&2; exit 2; }
mkdir -p "$STATE_DIR" "$BACKUP_DIR"
TAG_FILE="$STATE_DIR/${ENVIRONMENT}.tag"
PREVIOUS_TAG="$(cat "$TAG_FILE" 2>/dev/null || true)"

wait_healthy() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT_S))
  until curl -fsk --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; do
    if [ "$SECONDS" -ge "$deadline" ]; then return 1; fi
    sleep 3
  done
}

backup_db() {
  # Only when a database container is already running (not on the very first deploy).
  if compose ps --status running postgres 2>/dev/null | grep -q postgres; then
    local out="/backups/pre-${TAG}-$(date +%Y%m%d%H%M%S).dump"
    echo "== pg_dump -> $out"
    compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f '"$out"
  else
    echo "== no running database, skipping backup (first deploy)"
  fi
}

rotate_backups() {
  { ls -1t "$BACKUP_DIR"/pre-*.dump 2>/dev/null || true; } | tail -n +"$((KEEP_BACKUPS + 1))" | xargs -r rm -f --
}

rollback() {
  if [ -z "$PREVIOUS_TAG" ]; then
    echo "!! no previous tag recorded, cannot roll back; stack left as is" >&2
    return 1
  fi
  echo "!! rolling back to $PREVIOUS_TAG"
  IMAGE_TAG="$PREVIOUS_TAG" compose up -d --remove-orphans
  if wait_healthy; then
    echo "rollback to $PREVIOUS_TAG healthy"
  else
    echo "!! rollback did not become healthy either, manual intervention required" >&2
  fi
}

echo "== deploying $TAG to $ENVIRONMENT (previous: ${PREVIOUS_TAG:-none})"
export IMAGE_TAG="$TAG"

compose pull backend frontend
backup_db

if ! compose up -d --remove-orphans; then
  echo "!! compose up failed" >&2
  rollback || true
  exit 1
fi

if wait_healthy; then
  echo "$TAG" > "$TAG_FILE"
  echo "$PREVIOUS_TAG" > "$STATE_DIR/${ENVIRONMENT}.previous"
  rotate_backups
  echo "== $TAG is healthy on $ENVIRONMENT"
else
  echo "!! $TAG did not become healthy within ${HEALTH_TIMEOUT_S}s" >&2
  compose logs --tail 80 backend >&2 || true
  rollback || true
  exit 1
fi
