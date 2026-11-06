#!/usr/bin/env bash
# Smoke GET /health and assert dual-stack identity fields.
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

echo "==> GET ${HEALTH_URL} (expect stack=${EXPECT_STACK})"
BODY="$(curl -fsS --retry 5 --retry-delay 2 "${HEALTH_URL}")"
echo "$BODY"

printf '%s' "$BODY" | python3 -c '
import json, sys
expect_stack, expect_project, expect_payments = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(sys.stdin)
assert data.get("status") == "ok", data
assert data.get("service") == "firmshake-api", data
assert data.get("stack") == expect_stack, data
assert data.get("firebaseProjectId") == expect_project, data
payments = data.get("paymentsEnabled")
expect_bool = expect_payments.lower() == "true"
assert payments is expect_bool, data
print(f"OK: health stack={expect_stack} project={expect_project} paymentsEnabled={payments}")
' "$EXPECT_STACK" "$EXPECT_PROJECT" "$EXPECT_PAYMENTS"
