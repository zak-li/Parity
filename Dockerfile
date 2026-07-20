# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Best practices: no bytecode, unbuffered logs, run as non-root.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN useradd --create-home --uid 10001 parity
WORKDIR /app

# Copy packaging metadata + source, then install runtime extras only.
COPY pyproject.toml README.md LICENSE ./
COPY core ./core
COPY api ./api
COPY db ./db
COPY ai ./ai
# mlflow-skinny is the lightweight tracking client (no server deps) used by the
# engines to log runs; the MLflow server runs in its own container.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install ".[api,db,ai]" "mlflow-skinny>=2.15,<4"

# Alembic config (migrations live under db/migrations, copied with the db package).
# Run `alembic upgrade head` before starting in production.
COPY alembic.ini ./

USER parity
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
