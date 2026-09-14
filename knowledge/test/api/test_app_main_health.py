from fastapi import APIRouter
from fastapi.testclient import TestClient

from knowledge.api import app_main


def test_unified_api_health_returns_healthy(monkeypatch):
    monkeypatch.setattr(app_main, "load_domain_routers", lambda: [])
    client = TestClient(app_main.create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "service": "kb-platform"}


def test_create_app_mounts_converged_domain_routes(monkeypatch):
    import_router = APIRouter()
    query_router = APIRouter()
    metrics_router = APIRouter(prefix="/metrics")

    @import_router.post("/upload")
    def upload():
        return {"ok": True}

    @query_router.post("/query")
    def query():
        return {"ok": True}

    @metrics_router.get("/overview")
    def overview():
        return {"ok": True}

    monkeypatch.setattr(
        app_main,
        "load_domain_routers",
        lambda: [import_router, query_router, metrics_router],
    )
    client = TestClient(app_main.create_app())

    assert client.get("/api/health").status_code == 200
    assert client.post("/api/upload").json() == {"ok": True}
    assert client.post("/api/query").json() == {"ok": True}
    assert client.get("/api/metrics/overview").json() == {"ok": True}


def test_default_app_does_not_expose_legacy_upload_query():
    client = TestClient(app_main.create_app())
    assert client.post("/api/upload").status_code == 404
    assert client.post("/api/query").status_code == 404
