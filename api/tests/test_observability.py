from __future__ import annotations

from fastapi.testclient import TestClient

from api import create_app


def test_request_id_header_is_present():
    with TestClient(create_app()) as client:
        response = client.get("/health")
        assert response.headers.get("X-Request-ID")


def test_request_id_is_echoed_when_provided():
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
        assert response.headers["X-Request-ID"] == "trace-abc-123"


def test_metrics_endpoint_exposes_prometheus_format():
    with TestClient(create_app()) as client:
        client.get("/health")
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
        assert "parity_requests_total" in response.text


def test_metrics_endpoint_is_not_rate_limited():
    with TestClient(create_app()) as client:
        for _ in range(3):
            assert client.get("/metrics").status_code == 200
