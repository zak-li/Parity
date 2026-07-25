#!/usr/bin/env bash
# Make the (possibly root-owned) named volume writable by the mlflow user, then
# drop privileges and start the tracking server. All flags come from the ENV
# defaults in the Dockerfile and can be overridden at run time.
set -euo pipefail

chown -R mlflow:mlflow /mlflow 2>/dev/null || true

exec gosu mlflow mlflow server \
  --host "${MLFLOW_HOST}" \
  --port "${MLFLOW_PORT}" \
  --workers "${MLFLOW_WORKERS}" \
  --backend-store-uri "${MLFLOW_BACKEND_STORE_URI}" \
  --artifacts-destination "${MLFLOW_ARTIFACT_ROOT}" \
  --serve-artifacts \
  --gunicorn-opts "--timeout 120"
