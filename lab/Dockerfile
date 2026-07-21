# syntax=docker/dockerfile:1
# Self-contained MLflow tracking server for the Parity engines.
FROM python:3.12-slim

LABEL org.opencontainers.image.title="parity-mlflow" \
      org.opencontainers.image.description="MLflow tracking server for Parity" \
      org.opencontainers.image.source="https://github.com/zak-li/Parity"

# Server config — override any of these at run time (no rebuild needed), e.g.
# point MLFLOW_BACKEND_STORE_URI at PostgreSQL for durable, backed-up runs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MLFLOW_HOST=0.0.0.0 \
    MLFLOW_PORT=5000 \
    MLFLOW_WORKERS=1 \
    MLFLOW_BACKEND_STORE_URI=sqlite:////mlflow/mlflow.db \
    MLFLOW_ARTIFACT_ROOT=/mlflow/artifacts

# gosu enables the chown-then-drop-privileges pattern so the server runs as a
# non-root user while still owning a fresh (root-owned) named volume.
RUN --mount=type=cache,target=/root/.cache/pip \
    apt-get update \
 && apt-get install -y --no-install-recommends gosu \
 && rm -rf /var/lib/apt/lists/* \
 && pip install "mlflow==2.17.2" \
 && useradd --create-home --uid 10001 mlflow \
 && mkdir -p /mlflow/artifacts \
 && chown -R mlflow:mlflow /mlflow

WORKDIR /mlflow
EXPOSE 5000

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=10 \
    CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('MLFLOW_PORT','5000')).status==200 else 1)"

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
