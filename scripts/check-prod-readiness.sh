#!/usr/bin/env bash
# Thin wrapper → sibling firmshake cross-repo prod readiness dry-run.
# Prefer running from the web repo: npm run check:prod-readiness
# Never deploys. Never invents secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB_ROOT="${FIRMSHAKE_WEB_ROOT:-$ROOT/../firmshake}"
SCRIPT="$WEB_ROOT/scripts/check-prod-readiness.sh"

if [[ ! -f "$SCRIPT" ]]; then
  echo "ERROR: Sibling web readiness script missing: $SCRIPT" >&2
  echo "  Set FIRMSHAKE_WEB_ROOT or clone firmshake next to firmshake-api." >&2
  exit 2
fi

export FIRMSHAKE_API_ROOT="$ROOT"
exec bash "$SCRIPT"
