#!/usr/bin/env bash
# One-time bootstrap of a deploy host (run as root): directories, permissions, env file template.
# Usage: sudo ./deploy/setup-server.sh <staging|production> [deploy-user]
set -euo pipefail

ENVIRONMENT="${1:?usage: setup-server.sh <staging|production> [deploy-user]}"
DEPLOY_USER="${2:-runner}"
case "$ENVIRONMENT" in staging|production) ;; *) echo "environment must be staging or production" >&2; exit 2 ;; esac
[ "$(id -u)" -eq 0 ] || { echo "run as root" >&2; exit 2; }
id "$DEPLOY_USER" >/dev/null 2>&1 || { echo "user $DEPLOY_USER does not exist" >&2; exit 2; }

for tool in podman docker-compose curl; do
  command -v "$tool" >/dev/null 2>&1 || echo "WARNING: $tool not found in PATH" >&2
done

install -d -m 750 -o "$DEPLOY_USER" /etc/intake /etc/intake/tls /etc/intake/smcb
install -d -m 750 -o "$DEPLOY_USER" /var/lib/intake /var/backups/intake

ENV_FILE="/etc/intake/${ENVIRONMENT}.env"
if [ ! -e "$ENV_FILE" ]; then
  cp "$(dirname "$0")/prod.env.example" "$ENV_FILE"
  chown "$DEPLOY_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "created $ENV_FILE - replace every CHANGE_ME and the real hostnames"
fi

[ -e /etc/intake/tls/fullchain.pem ] || echo "TODO: place fullchain.pem and privkey.pem in /etc/intake/tls"
[ -d /etc/intake/smcb ] && [ -n "$(ls -A /etc/intake/smcb)" ] || echo "TODO: place the SMC-B certificate in /etc/intake/smcb"
grep -q CHANGE_ME "$ENV_FILE" && echo "TODO: $ENV_FILE still contains CHANGE_ME"
echo "bootstrap done for $ENVIRONMENT"
