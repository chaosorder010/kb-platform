from __future__ import annotations

from fastapi.testclient import TestClient

from knowledge.api import app_main, auth_router, deps, settlement_router
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService
from knowledge.qa.access_logs import MemoryQaAccessLogRepository, build_access_log_entry
from knowledge.settlement.embeddings import HashingEmbedder
from knowledge.settlement.faqs import MemoryFaqRepository
from knowledge.settlement.gaps import MemoryGapRepository
from knowledge.settlement.service import SettlementService
from knowledge.units.repository import MemoryKnowledgeRepository
from knowledge.units.service import KnowledgeService


def _seeded_auth() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _client(monkeypatch):
    auth_service = AuthService(repository=_seeded_auth())
    logs = MemoryQaAccessLogRepository()
    knowledge = KnowledgeService(repository=MemoryKnowledgeRepository())
    settlement = SettlementService(
        faqs=MemoryFaqRepository(),
        gaps=MemoryGapRepository(),
        access_logs=logs,
        embedder=HashingEmbedder(),
        knowledge_service=knowledge,
        mine_threshold=0.5,
        min_cluster_size=1,
    )
    monkeypatch.setattr(
        app_main,
        "load_domain_routers",
        lambda: [auth_router.router, settlement_router.router],
    )
    app = app_main.create_app()
    app.dependency_overrides[deps.get_auth_service] = lambda: auth_service
    app.dependency_overrides[settlement_router.get_settlement_service] = (
        lambda: settlement
    )
    return TestClient(app), logs, knowledge


def test_is_gap_entry_low_confidence_and_permission_miss():
    settlement = SettlementService(
        faqs=MemoryFaqRepository(),
        gaps=MemoryGapRepository(),
        access_logs=MemoryQaAccessLogRepository(),
        embedder=HashingEmbedder(),
        gap_recall_threshold=0.45,
    )
    assert not settlement._is_gap_entry(
        build_access_log_entry(
            session_id="s",
            user_id="u",
            question="有权限作答",
            answer="ok",
            recalled_unit_ids=["ku-1"],
            authorized_unit_ids=["ku-1"],
            unauthorized_unit_ids=[],
        )
    )
    assert not settlement._is_gap_entry(
        build_access_log_entry(
            session_id="s",
            user_id="u",
            question="仅权限缺失",
            answer="无权限",
            recalled_unit_ids=["ku-1"],
            authorized_unit_ids=[],
            unauthorized_unit_ids=["ku-1"],
            max_recall_score=0.9,
        )
    )
    assert settlement._is_gap_entry(
        build_access_log_entry(
            session_id="s",
            user_id="u",
            question="低置信命中",
            answer="不确定",
            recalled_unit_ids=["ku-1"],
            authorized_unit_ids=[],
            unauthorized_unit_ids=[],
            max_recall_score=0.1,
        )
    )
    assert settlement._is_gap_entry(
        build_access_log_entry(
            session_id="s",
            user_id="u",
            question="完全未命中",
            answer="不知道",
            recalled_unit_ids=[],
            authorized_unit_ids=[],
            unauthorized_unit_ids=[],
        )
    )


def test_knowledge_gaps_mine_create_unit_and_status(monkeypatch):
    client, logs, knowledge = _client(monkeypatch)
    bob = _login(client, "bob", "User@123")
    assert (
        client.get("/api/settlement/knowledge-gaps", headers=_auth(bob)).status_code
        == 403
    )

    for q in ["未知故障码 E99", "未知故障码E99怎么办", "完全无关的问题"]:
        logs.insert(
            build_access_log_entry(
                session_id="s",
                user_id="user-bob",
                question=q,
                answer="无权限或未命中",
                recalled_unit_ids=[],
                authorized_unit_ids=[],
                unauthorized_unit_ids=[],
                total_tokens=3,
                response_time_ms=40,
            )
        )

    token = _login(client, "kbadmin", "Kb@123456")
    gaps = client.get(
        "/api/settlement/knowledge-gaps?refresh=true",
        headers=_auth(token),
    )
    assert gaps.status_code == 200
    items = gaps.json()["items"]
    assert items
    assert all("question_pattern" in g for g in items)
    assert all("ask_count" in g for g in items)
    assert all("last_asked_at" in g for g in items)
    assert all(g.get("status") == "unresolved" for g in items)

    target = max(items, key=lambda g: g["ask_count"])
    created = client.post(
        f"/api/settlement/knowledge-gaps/{target['id']}/create-unit",
        headers=_auth(token),
        json={"title": "E99 故障说明"},
    )
    assert created.status_code == 200
    body = created.json()
    assert body["gap"]["status"] == "resolved"
    assert body["unit"]["id"]
    assert knowledge.get_unit(body["unit"]["id"]) is not None
    assert body["gap"]["resolved_unit_id"] == body["unit"]["id"]

    other = next(g for g in items if g["id"] != target["id"])
    ignored = client.post(
        f"/api/settlement/knowledge-gaps/{other['id']}/status",
        headers=_auth(token),
        json={"status": "ignored"},
    )
    assert ignored.status_code == 200
    assert ignored.json()["status"] == "ignored"

    resolved = client.post(
        f"/api/settlement/knowledge-gaps/{target['id']}/status",
        headers=_auth(token),
        json={"status": "resolved"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
