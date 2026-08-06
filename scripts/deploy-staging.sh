#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="us-central1-docker.pkg.dev/firmshake-dev/firmshake/api:staging-latest"

cd "$ROOT"

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
