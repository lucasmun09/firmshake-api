#!/usr/bin/env bash
# Deploy API to prod (firmshake-prod / us-east1).
# Requires: firmshake-prod project, Artifact Registry, Cloud Run service, .cloudrun.env.prod.yaml filled in.
# See firmshake/docs/devo-prod-stacks.md.
# Refuses REPLACE_ME placeholders and firmshake-dev project wiring.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ID="${FIREBASE_PROJECT_ID:-firmshake-prod}"
REGION="${CLOUD_RUN_REGION:-us-east1}"
SERVICE="${CLOUD_RUN_SERVICE:-firmshake-api}"
REPOSITORY="${ARTIFACT_REPOSITORY:-firmshake}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/api:prod-latest"
ENV_FILE="${ROOT}/.cloudrun.env.prod.yaml"

cd "$ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  exit 1
fi

if [[ "$PROJECT_ID" != "firmshake-prod" ]]; then
  echo "ERROR: Refusing prod API deploy — FIREBASE_PROJECT_ID=${PROJECT_ID} (expected firmshake-prod)." >&2
  exit 1
fi

# Fail closed on placeholders / deovo cross-wire / payments / CORS.
bash "$ROOT/scripts/assert-cloudrun-env.sh" prod "$ENV_FILE"

echo "Building linux/amd64 image for prod (${REGION})..."
docker build --platform linux/amd64 -t "$IMAGE" .

echo "Pushing image..."
docker push "$IMAGE"

echo "Deploying to Cloud Run (${SERVICE})..."
gcloud run deploy "$SERVICE" \
  --image "$IMAGE" \
  --region "$REGION" \
  --project "$PROJECT_ID" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --env-vars-file "$ENV_FILE"

URL="$(gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --format='value(status.url)' 2>/dev/null || true)"
echo "Done."
if [[ -n "$URL" ]]; then
  echo "  Cloud Run URL: $URL"
  echo "  Set web VITE_API_BASE_URL to that URL in .env.production.local + GitHub Environment prod, then:"
  echo "    cd ../firmshake && npm run deploy:prod"
else
  echo "  Resolve the service URL with:"
  echo "    gcloud run services describe ${SERVICE} --region ${REGION} --project ${PROJECT_ID} --format='value(status.url)'"
fi
