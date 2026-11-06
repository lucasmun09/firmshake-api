#!/usr/bin/env bash
# Deploy API to deovo / staging (firmshake-dev, us-central1).
# Alias: scripts/deploy-devo.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="us-central1-docker.pkg.dev/firmshake-dev/firmshake/api:staging-latest"

cd "$ROOT"

bash "$ROOT/scripts/assert-cloudrun-env.sh" deovo "$ROOT/.cloudrun.env.yaml"

echo "Building linux/amd64 image..."
docker build --platform linux/amd64 -t "$IMAGE" .

echo "Pushing image..."
docker push "$IMAGE"

echo "Deploying to Cloud Run..."
gcloud run deploy firmshake-api-staging \
  --image "$IMAGE" \
  --region us-central1 \
  --project firmshake-dev \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --env-vars-file "$ROOT/.cloudrun.env.yaml"

echo "Done: https://firmshake-api-staging-858269838319.us-central1.run.app"
