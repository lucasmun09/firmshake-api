#!/usr/bin/env bash
# Dry-run dual-stack env asserts (no docker / gcloud / deploy).
# Usage:
#   preflight-api.sh deovo
#   preflight-api.sh prod
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STACK="${1:-}"

if [[ -z "$STACK" ]]; then
  echo "Usage: $0 deovo|prod" >&2
  exit 2
fi

case "$STACK" in
  deovo|devo|staging)
    bash "$ROOT/scripts/assert-cloudrun-env.sh" deovo "$ROOT/.cloudrun.env.yaml"
    ;;
  prod|production)
    bash "$ROOT/scripts/assert-cloudrun-env.sh" prod "$ROOT/.cloudrun.env.prod.yaml"
    ;;
  *)
    echo "Unknown stack: $STACK" >&2
    exit 2
    ;;
esac

echo "Preflight OK for ${STACK} (env assert only — no deploy)."
