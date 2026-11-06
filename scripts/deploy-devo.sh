#!/usr/bin/env bash
# Deploy API to deovo (firmshake-dev / staging). Alias for deploy-staging.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT/scripts/deploy-staging.sh"
