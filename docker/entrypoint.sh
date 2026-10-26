#!/bin/sh
# Start the API. One worker on purpose: the model is loaded in this process, and job state is
# in-process until persistence is added. CORS_ORIGINS must be set for browsers to reach the API.
set -eu

# If the weights were baked into the image, never reach out to the network for them at runtime.
if [ -f "${HF_HOME:-/opt/model-cache}/model_manifest.json" ]; then
  export HF_HUB_OFFLINE=1
fi

if [ -z "${CORS_ORIGINS:-}" ]; then
  echo "WARNING: CORS_ORIGINS is not set; the API only accepts browser calls from http://localhost:3000. Set it to the frontend origin." >&2
fi

cd /app/backend
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8080}" --workers 1 --proxy-headers
