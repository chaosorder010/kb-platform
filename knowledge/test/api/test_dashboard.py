from __future__ import annotations

from fastapi.testclient import TestClient

from knowledge.api import app_main, auth_router, dashboard_router, deps
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService
from knowledge.dashboard.service import DashboardService
from knowledge.qa.access_logs import MemoryQaAccessLogRepository, build_access_log_entry


def _seeded_auth() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )


def _client(monkeypatch, logs: MemoryQaAccessLogRepository, unit_total: int = 3):
    auth_repo = _seeded_auth()
    auth_service = AuthService(repository=auth_repo)
    titles = {"ku-1": "手册A", "ku-2": "手册B"}

    service = DashboardService(
        access_logs=logs,
        unit_counter=lambda: unit_total,
        unit_title_lookup=lambda uid: titles.get(uid, uid),
    )

    monkeypatch.setattr(
        app_main,
        "load_domain_routers",
        lambda: [auth_router.router, dashboard_router.router],
    )
    app = app_main.create_app()
    app.dependency_overrides[deps.get_auth_service] = lambda: auth_service
    app.dependency_overrides[dashboard_router.get_dashboard_service] = lambda: service
    return TestClient(app)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_logs(logs: MemoryQaAccessLogRepository) -> None:
    samples = [
        build_access_log_entry(
            session_id="s1",
            user_id="user-alice",
            question="怎么检修？",
            answer="先断电",
            recalled_unit_ids=["ku-1", "ku-2"],
            authorized_unit_ids=["ku-1"],
            unauthorized_unit_ids=["ku-2"],
            total_tokens=20,
            response_time_ms=120,
        ),
        build_access_log_entry(
            session_id="s2",
            user_id="user-bob",
            question="怎么检修？",
            answer="无权限",
            recalled_unit_ids=["ku-1"],
            authorized_unit_ids=[],
            unauthorized_unit_ids=["ku-1"],
            total_tokens=8,
            response_time_ms=80,
        ),
        build_access_log_entry(
            session_id="s3",
            user_id="user-alice",
            question="如何校准？",
            answer="按手册",
            recalled_unit_ids=["ku-2"],
            authorized_unit_ids=["ku-2"],
            unauthorized_unit_ids=[],
            total_tokens=12,
            response_time_ms=450,
        ),
    ]
    samples[0]["created_at"] = "2026-03-01T10:00:00+00:00"
    samples[1]["created_at"] = "2026-03-01T12:00:00+00:00"
    samples[2]["created_at"] = "2026-03-08T09:00:00+00:00"
    for item in samples:
        logs.insert(item)


def test_dashboard_requires_auth_and_permission(monkeypatch):
    logs = MemoryQaAccessLogRepository()
    client = _client(monkeypatch, logs)
    assert client.get("/api/dashboard/metrics").status_code == 401

    bob = _login(client, "bob", "User@123")
    denied = client.get("/api/dashboard/metrics", headers=_auth(bob))
    assert denied.status_code == 403


def test_dashboard_metrics_and_rankings_match_logs(monkeypatch):
    logs = MemoryQaAccessLogRepository()
    _seed_logs(logs)
    client = _client(monkeypatch, logs, unit_total=5)
    token = _login(client, "admin", "Admin@123")

    metrics = client.get("/api/dashboard/metrics", headers=_auth(token)).json()
    assert metrics["visit_count"] == 3
    assert metrics["uv"] == 2
    assert metrics["knowledge_unit_count"] == 5
    assert metrics["total_tokens"] == 40
    assert metrics["avg_response_time_ms"] == round((120 + 80 + 450) / 3, 2)

    questions = client.get(
        "/api/dashboard/rankings/questions",
        headers=_auth(token),
    ).json()["items"]
    assert questions[0]["question"] == "怎么检修？"
    assert questions[0]["count"] == 2

    units = client.get(
        "/api/dashboard/rankings/units",
        headers=_auth(token),
    ).json()["items"]
    assert {u["unit_id"] for u in units} == {"ku-1", "ku-2"}
    assert units[0]["count"] == 1
    assert any(u["title"] == "手册A" for u in units)


def test_dashboard_token_stats_day_and_week(monkeypatch):
    logs = MemoryQaAccessLogRepository()
    _seed_logs(logs)
    client = _client(monkeypatch, logs)
    token = _login(client, "kbadmin", "Kb@123456")

    day = client.get(
        "/api/dashboard/stats/tokens?granularity=day",
        headers=_auth(token),
    ).json()
    assert day["granularity"] == "day"
    assert len(day["trend"]) == 2
    assert day["trend"][0]["bucket"] == "2026-03-01"
    assert day["trend"][0]["visit_count"] == 2
    assert day["trend"][0]["total_tokens"] == 28
    assert sum(b["count"] for b in day["response_time_distribution"]) == 3

    week = client.get(
        "/api/dashboard/stats/tokens?granularity=week",
        headers=_auth(token),
    ).json()
    assert week["granularity"] == "week"
    assert len(week["trend"]) >= 1
    assert sum(item["visit_count"] for item in week["trend"]) == 3
