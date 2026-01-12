import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "BCom AI Services API"


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_docs_available():
    response = client.get("/docs")
    assert response.status_code == 200


def test_unauthorized_access():
    response = client.post("/api/v1/anomaly-detection/detect", json={
        "anomaly_type": "network",
        "data": []
    })
    assert response.status_code == 403


def test_api_structure():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "docs" in data
