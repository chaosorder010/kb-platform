from fastapi.testclient import TestClient

from knowledge.api.app_main import create_app


def test_unified_api_health_returns_healthy():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "kb-platform"}

