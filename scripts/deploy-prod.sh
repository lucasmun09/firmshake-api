#!/usr/bin/env bash
# Deploy API to prod (firmshake-prod / us-east1).
# Requires: firmshake-prod project, Artifact Registry, Cloud Run service, .cloudrun.env.prod.yaml filled in.
# See ../docs or firmshake/docs/devo-prod-stacks.md.
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

echo "Done. Resolve the service URL with:"
echo "  gcloud run services describe ${SERVICE} --region ${REGION} --project ${PROJECT_ID} --format='value(status.url)'"
