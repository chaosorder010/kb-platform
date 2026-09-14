from __future__ import annotations

from fastapi.testclient import TestClient

from knowledge.api import (
    app_main,
    ai_router,
    auth_router,
    deps,
    settlement_router,
)
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService
from knowledge.qa.access_logs import MemoryQaAccessLogRepository, build_access_log_entry
from knowledge.qa.service import ChatService
from knowledge.settlement.embeddings import HashingEmbedder
from knowledge.settlement.faqs import MemoryFaqRepository
from knowledge.settlement.service import SettlementService
from knowledge.units.repository import MemoryKnowledgeRepository
from knowledge.units.service import KnowledgeService
from knowledge.utils.sse_util import SSEEvent
import json


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


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in [b for b in raw.split("\n\n") if b.strip()]:
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        events.append((event_name, json.loads("\n".join(data_lines) or "{}")))
    return events


def _client(monkeypatch):
    auth_service = AuthService(repository=_seeded_auth())
    logs = MemoryQaAccessLogRepository()
    faqs = MemoryFaqRepository()
    settlement = SettlementService(
        faqs=faqs,
        access_logs=logs,
        embedder=HashingEmbedder(),
        mine_threshold=0.5,
        cache_threshold=0.8,
        min_cluster_size=2,
    )
    knowledge = KnowledgeService(repository=MemoryKnowledgeRepository())

    def boom(state: dict):
        raise AssertionError("graph should not run on FAQ cache hit")

    chat = ChatService(
        knowledge_service=knowledge,
        access_logs=logs,
        graph_runner=boom,
        faq_matcher=settlement.match_cache,
    )

    monkeypatch.setattr(
        app_main,
        "load_domain_routers",
        lambda: [auth_router.router, settlement_router.router, ai_router.router],
    )
    app = app_main.create_app()
    app.dependency_overrides[deps.get_auth_service] = lambda: auth_service
    app.dependency_overrides[settlement_router.get_settlement_service] = (
        lambda: settlement
    )
    app.dependency_overrides[ai_router.get_chat_service] = lambda: chat
    return TestClient(app), logs, settlement, faqs


def test_faq_mine_review_publish_and_cache_hit(monkeypatch):
    client, logs, settlement, faqs = _client(monkeypatch)

    bob = _login(client, "bob", "User@123")
    denied = client.get("/api/settlement/faqs/recommendations", headers=_auth(bob))
    assert denied.status_code == 403

    for q in ["怎么检修？", "怎么检修设备？", "如何校准？"]:
        logs.insert(
            build_access_log_entry(
                session_id="s",
                user_id="user-alice",
                question=q,
                answer=f"答：{q}",
                recalled_unit_ids=["ku-1"],
                authorized_unit_ids=["ku-1"],
                unauthorized_unit_ids=[],
                total_tokens=10,
                response_time_ms=50,
            )
        )

    token = _login(client, "kbadmin", "Kb@123456")
    rec = client.get(
        "/api/settlement/faqs/recommendations",
        headers=_auth(token),
    )
    assert rec.status_code == 200
    items = rec.json()["items"]
    assert items
    target = items[0]
    assert target["status"] == "pending_review"
    assert target["hit_count"] >= 2
    assert target.get("related_unit_id") == "ku-1" or "ku-1" in (
        target.get("related_unit_ids") or []
    )
    assert target.get("answer")

    reviewed = client.post(
        f"/api/settlement/faqs/{target['id']}/review",
        headers=_auth(token),
        json={"action": "approve", "edited_answer": "标准检修步骤：断电后操作。"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "published"
    assert reviewed.json()["cache_enabled"] is True

    published = client.get(
        "/api/settlement/faqs?status=published",
        headers=_auth(token),
    ).json()["items"]
    assert any(i["id"] == target["id"] for i in published)

    with client.stream(
        "POST",
        "/api/ai/chat/stream",
        headers=_auth(token),
        json={"question": target["question"], "session_id": "faq-sess"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())
    events = _parse_sse(raw)
    final = next(payload for name, payload in events if name == SSEEvent.FINAL)
    assert final.get("faq_cache_hit") is True
    assert "断电" in final["answer"]
