#!/usr/bin/env bash
# Usage: deploy/smoke-test.sh <base-url>   e.g. https://intake.klinik.local
# Black-box checks after a deployment. Exit code != 0 fails the pipeline.
set -uo pipefail

BASE="${1:?base url}"
CURL_OPTS=(-s --max-time 10)
[ -n "${CA_CERT:-}" ] && CURL_OPTS+=(--cacert "$CA_CERT") || CURL_OPTS+=(-k)
fail=0

check() { # name expected-codes(regex) actual
  if [[ "$3" =~ ^($2)$ ]]; then echo "ok   $1 ($3)"; else echo "FAIL $1 (got $3, want $2)"; fail=1; fi
}

code() { curl "${CURL_OPTS[@]}" -o /dev/null -w '%{http_code}' "$@"; }

check "health"                     "200" "$(code "$BASE/health")"
check "frontend served"            "200" "$(code "$BASE/")"
check "http redirects to https"    "301" "$(curl -s --max-time 10 -o /dev/null -w '%{http_code}' "http://${BASE#https://}/")"
# Auth must be enforced: no token -> rejected, never 200
check "chat requires token"        "401|403" "$(code -X POST -H 'Content-Type: application/json' -d '{"message":"hi"}' "$BASE/api/chat")"
check "consent requires token"     "401|403" "$(code -X POST -H 'Content-Type: application/json' -d '{}' "$BASE/api/consent")"
check "security header HSTS"       "1" "$(curl "${CURL_OPTS[@]}" -I "$BASE/" | grep -ci '^strict-transport-security')"

exit $fail
