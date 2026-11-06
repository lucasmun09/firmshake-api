#!/usr/bin/env bash
# Smoke GET /health (+ /ready) and assert dual-stack identity fields.
# Usage:
#   smoke-health.sh <base_url> deovo
#   smoke-health.sh <base_url> prod
set -euo pipefail

URL_BASE="${1:-}"
EXPECT_STACK="${2:-}"

if [[ -z "$URL_BASE" || -z "$EXPECT_STACK" ]]; then
  echo "Usage: $0 <api_base_url> deovo|prod" >&2
  exit 2
fi

URL_BASE="${URL_BASE%/}"
HEALTH_URL="${URL_BASE}/health"
READY_URL="${URL_BASE}/ready"

case "$EXPECT_STACK" in
  deovo|devo)
    EXPECT_STACK=devo
    EXPECT_PROJECT=firmshake-dev
    EXPECT_PAYMENTS=true
    ;;
  prod|production)
    EXPECT_STACK=prod
    EXPECT_PROJECT=firmshake-prod
    EXPECT_PAYMENTS=false
    ;;
  *)
    echo "Unknown expected stack: $EXPECT_STACK" >&2
    exit 2
    ;;
esac

assert_payload() {
  local label="$1"
  local body="$2"
  local require_ready="$3"
  printf '%s' "$body" | python3 -c '
import json, sys
expect_stack, expect_project, expect_payments, label, require_ready = sys.argv[1:6]
data = json.load(sys.stdin)
assert data.get("status") == "ok", data
assert data.get("service") == "firmshake-api", data
assert data.get("stack") == expect_stack, data
assert data.get("firebaseProjectId") == expect_project, data
payments = data.get("paymentsEnabled")
expect_bool = expect_payments.lower() == "true"
assert payments is expect_bool, data
if require_ready.lower() == "true":
    assert data.get("ready") is True, data
print(f"OK: {label} stack={expect_stack} project={expect_project} paymentsEnabled={payments}")
' "$EXPECT_STACK" "$EXPECT_PROJECT" "$EXPECT_PAYMENTS" "$label" "$require_ready"
}

echo "==> GET ${HEALTH_URL} (expect stack=${EXPECT_STACK})"
BODY="$(curl -fsS --retry 5 --retry-delay 2 "${HEALTH_URL}")"
echo "$BODY"
assert_payload "health" "$BODY" "false"

echo "==> GET ${READY_URL} (expect stack=${EXPECT_STACK}, ready=true)"
READY_BODY="$(curl -fsS --retry 5 --retry-delay 2 "${READY_URL}")"
echo "$READY_BODY"
assert_payload "ready" "$READY_BODY" "true"
