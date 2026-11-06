#!/usr/bin/env bash
# Assert a Cloud Run env YAML matches the intended FirmShake API stack.
# Usage:
#   assert-cloudrun-env.sh deovo [.cloudrun.env.yaml]
#   assert-cloudrun-env.sh prod [.cloudrun.env.prod.yaml]
set -euo pipefail

STACK="${1:-}"
ENV_FILE="${2:-}"

if [[ -z "$STACK" ]]; then
  echo "Usage: $0 deovo|prod [env_yaml]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

yaml_val() {
  local file="$1"
  local key="$2"
  sed -n "s/^${key}:[[:space:]]*//p" "$file" | head -n1 | sed "s/^['\"]//;s/['\"]$//" | tr -d '\r'
}

assert_devo() {
  local file="${1:-$ROOT/.cloudrun.env.yaml}"
  if [[ ! -f "$file" ]]; then
    echo "ERROR: env file missing: $file" >&2
    exit 1
  fi
  local project_id gcs cors payments
  project_id="$(yaml_val "$file" FIREBASE_PROJECT_ID)"
  gcs="$(yaml_val "$file" GCS_BUCKET)"
  cors="$(yaml_val "$file" CORS_ORIGINS)"
  payments="$(yaml_val "$file" PAYMENTS_ENABLED)"

  if [[ "$project_id" != "firmshake-dev" ]]; then
    echo "ERROR: Refusing deovo — FIREBASE_PROJECT_ID=${project_id:-<unset>} (expected firmshake-dev)" >&2
    exit 1
  fi
  if [[ "$gcs" != "firmshake-dev-images" ]]; then
    echo "ERROR: Refusing deovo — GCS_BUCKET=${gcs:-<unset>} (expected firmshake-dev-images)" >&2
    exit 1
  fi
  if [[ "$cors" == *firmshake-prod.web.app* ]]; then
    echo "ERROR: Refusing deovo — CORS_ORIGINS must not include firmshake-prod Hosting." >&2
    exit 1
  fi
  if [[ "$cors" != *firmshake-controlpanel.web.app* ]]; then
    echo "ERROR: Refusing deovo — CORS_ORIGINS must include control panel (devo-only)." >&2
    exit 1
  fi
  if [[ -n "$payments" && "$payments" != "true" && "$payments" != "'true'" ]]; then
    echo "WARNING: deovo PAYMENTS_ENABLED=${payments} (usually true for mock deposits; no Stripe this phase)." >&2
  fi
  # Active (non-comment) lines must not point at prod project / placeholder Typesense.
  if grep -E "firmshake-prod-images|REPLACE_ME_PROD|YOUR-PROD-" "$file" | grep -v '^\s*#' >/dev/null; then
    echo "ERROR: Refusing deovo — active lines contain prod placeholders/values." >&2
    exit 1
  fi
  echo "OK: $file looks like deovo API env (firmshake-dev)."
}

assert_prod() {
  local file="${1:-$ROOT/.cloudrun.env.prod.yaml}"
  if [[ ! -f "$file" ]]; then
    echo "ERROR: env file missing: $file" >&2
    exit 1
  fi
  local project_id gcs cors payments
  project_id="$(yaml_val "$file" FIREBASE_PROJECT_ID)"
  gcs="$(yaml_val "$file" GCS_BUCKET)"
  cors="$(yaml_val "$file" CORS_ORIGINS)"
  payments="$(yaml_val "$file" PAYMENTS_ENABLED)"

  if [[ "$project_id" != "firmshake-prod" ]]; then
    echo "ERROR: Refusing prod — FIREBASE_PROJECT_ID=${project_id:-<unset>} (expected firmshake-prod)" >&2
    exit 1
  fi
  if [[ "$gcs" != "firmshake-prod-images" ]]; then
    echo "ERROR: Refusing prod — GCS_BUCKET=${gcs:-<unset>} (expected firmshake-prod-images)" >&2
    exit 1
  fi
  if [[ "$cors" == *firmshake-dev.web.app* || "$cors" == *firmshake-controlpanel* ]]; then
    echo "ERROR: Refusing prod — CORS_ORIGINS must not include deovo Hosting or control panel." >&2
    exit 1
  fi
  if [[ "$cors" != *firm-shake.com* || "$cors" != *firmshake-prod.web.app* ]]; then
    echo "ERROR: Refusing prod — CORS_ORIGINS must include firm-shake.com and firmshake-prod.web.app." >&2
    exit 1
  fi
  if [[ "$payments" != "false" && "$payments" != "'false'" ]]; then
    echo "ERROR: Refusing prod — PAYMENTS_ENABLED must be false (got: ${payments:-<unset>})." >&2
    exit 1
  fi
  # Dual-stack ships without a payment processor — refuse active Stripe keys.
  if grep -nE '^[[:space:]]*STRIPE_(SECRET_KEY|WEBHOOK_SECRET|PUBLISHABLE_KEY):' "$file" | grep -vE '^[0-9]+:[[:space:]]*#' >/dev/null; then
    echo "ERROR: Refusing prod — active STRIPE_* keys present (no processor this phase):" >&2
    grep -nE '^[[:space:]]*STRIPE_(SECRET_KEY|WEBHOOK_SECRET|PUBLISHABLE_KEY):' "$file" | grep -vE '^[0-9]+:[[:space:]]*#' >&2 || true
    echo "  Keep PAYMENTS_ENABLED=false and omit Stripe keys. See docs/dual-stack.md." >&2
    exit 1
  fi
  if grep -nE "REPLACE_ME|YOUR-PROD-|YOUR-DEVO-|firmshake-dev|firmshake-api-staging|firmshake-dev-images" "$file" | grep -vE '^[0-9]+:\s*#' >/dev/null; then
    echo "ERROR: Refusing prod — $file still has placeholders or deovo values in active lines:" >&2
    grep -nE "REPLACE_ME|YOUR-PROD-|YOUR-DEVO-|firmshake-dev|firmshake-api-staging|firmshake-dev-images" "$file" | grep -vE '^[0-9]+:\s*#' >&2 || true
    echo "  Fill RECAPTCHA_SITE_KEY (and Typesense when ready). Never reuse deovo Typesense/Firestore." >&2
    exit 1
  fi
  echo "OK: $file looks like prod API env (firmshake-prod, payments disabled)."
}

case "$STACK" in
  deovo|devo|staging)
    assert_devo "${ENV_FILE:-$ROOT/.cloudrun.env.yaml}"
    ;;
  prod|production)
    assert_prod "${ENV_FILE:-$ROOT/.cloudrun.env.prod.yaml}"
    ;;
  *)
    echo "Unknown stack mode: $STACK" >&2
    exit 2
    ;;
esac
