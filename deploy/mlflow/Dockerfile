# MLflow tracking server for the Parity engines.
FROM python:3.12-slim

RUN pip install --no-cache-dir "mlflow==2.17.2"

WORKDIR /mlflow
EXPOSE 5000

# SQLite backend store + local artifact root (persisted via a volume).
CMD ["mlflow", "server", \
     "--host", "0.0.0.0", "--port", "5000", \
     "--workers", "1", \
     "--backend-store-uri", "sqlite:////mlflow/mlflow.db", \
     "--artifacts-destination", "/mlflow/artifacts", \
     "--serve-artifacts"]
