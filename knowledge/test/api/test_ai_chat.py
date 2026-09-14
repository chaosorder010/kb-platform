from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from knowledge.api import app_main, ai_router, auth_router, deps, knowledge_router
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService
from knowledge.processor.query_processor.nodes.authz_filter_node import AuthzFilterNode
from knowledge.qa.access_logs import MemoryQaAccessLogRepository
from knowledge.qa.seed import EXAMPLE_UNIT_ID, seed_example_knowledge_unit
from knowledge.qa.service import ChatService
from knowledge.units.repository import MemoryKnowledgeRepository
from knowledge.units.service import KnowledgeService
from knowledge.utils.sse_util import SSEEvent


def _seeded_auth() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )


def _parse_sse(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    blocks = [b for b in raw.split("\n\n") if b.strip()]
    for block in blocks:
        event_name = "message"
        data_lines: list[str] = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        payload = json.loads("\n".join(data_lines) or "{}")
        events.append((event_name, payload))
    return events


def _fake_runner_factory(knowledge: KnowledgeService):
    def runner(state: dict) -> dict:
        task_id = state["task_id"]
        docs = [
            {
                "content": "授权手册：请先断电再检修。",
                "title": "示例产品安全手册",
                "unit_id": EXAMPLE_UNIT_ID,
                "chunk_id": 1,
                "source": "local",
                "score": 0.9,
            },
            {
                "content": "另一本无权限手册内容。",
                "title": "机密手册",
                "unit_id": "ku-secret-001",
                "chunk_id": 2,
                "source": "local",
                "score": 0.8,
            },
        ]
        state["reranked_docs"] = docs
        state["recalled_unit_ids"] = [EXAMPLE_UNIT_ID, "ku-secret-001"]

        AuthzFilterNode().process(state)

        authorized = state.get("reranked_docs") or []
        if authorized:
            answer = "根据授权知识：" + authorized[0]["content"]
        else:
            answer = "当前召回内容均无访问权限，无法基于知识库作答。"
        state["answer"] = answer
        state["prompt_tokens"] = 12
        state["completion_tokens"] = 8
        state["total_tokens"] = 20

        from knowledge.utils.sse_util import push_sse_event

        missing = state.get("unauthorized_units") or []
        if missing:
            push_sse_event(
                task_id=task_id,
                event=SSEEvent.PERMISSION_MISSING,
                data={"cards": missing},
            )
        if state.get("is_stream"):
            push_sse_event(
                task_id=task_id,
                event=SSEEvent.DELTA,
                data={"content": answer},
            )
            push_sse_event(
                task_id=task_id,
                event=SSEEvent.FINAL,
                data={
                    "answer": answer,
                    "unauthorized_units": missing,
                    "authorized_unit_ids": state.get("authorized_unit_ids") or [],
                    "references": [
                        {
                            "unit_id": d.get("unit_id"),
                            "title": d.get("title") or "",
                        }
                        for d in authorized
                    ],
                },
            )
        return state

    return runner


def _client(
    monkeypatch,
) -> tuple[TestClient, KnowledgeService, MemoryQaAccessLogRepository, dict]:
    auth_repo = _seeded_auth()
    auth_service = AuthService(repository=auth_repo)
    knowledge_repo = MemoryKnowledgeRepository()
    knowledge_service = KnowledgeService(repository=knowledge_repo)
    seed_example_knowledge_unit(knowledge_service)
    knowledge_repo.insert_unit(
        {
            "id": "ku-secret-001",
            "unit_code": "KU-SECRET-001",
            "title": "机密手册",
            "content": "机密",
            "summary": "",
            "category": "demo",
            "source_file_name": "secret.md",
            "file_type": "md",
            "file_size": 10,
            "status": "published",
            "creator_id": "user-kbadmin",
            "creator_name": "知识管理员",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "data_permissions": [],
            "permission_summary": "无数据权限",
            "tags": [],
            "attachments": [],
        }
    )
    logs = MemoryQaAccessLogRepository()
    history_store: dict[str, list[dict]] = {}

    def history_getter(session_id: str, limit: int = 50):
        items = history_store.get(session_id, [])
        return list(items[-limit:])

    def history_clearer(session_id: str) -> int:
        n = len(history_store.get(session_id, []))
        history_store.pop(session_id, None)
        return n

    chat_service = ChatService(
        knowledge_service=knowledge_service,
        access_logs=logs,
        graph_runner=_fake_runner_factory(knowledge_service),
        history_getter=history_getter,
        history_clearer=history_clearer,
    )

    monkeypatch.setattr(
        app_main,
        "load_domain_routers",
        lambda: [auth_router.router, knowledge_router.router, ai_router.router],
    )
    app = app_main.create_app()
    app.dependency_overrides[deps.get_auth_service] = lambda: auth_service
    app.dependency_overrides[knowledge_router.get_knowledge_service] = (
        lambda: knowledge_service
    )
    app.dependency_overrides[ai_router.get_chat_service] = lambda: chat_service
    return TestClient(app), knowledge_service, logs, history_store


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_unauthenticated_chat_returns_401(monkeypatch):
    client, _, _, _ = _client(monkeypatch)

    response = client.post(
        "/api/ai/chat/stream",
        json={"question": "怎么检修？", "session_id": "s1"},
    )
    assert response.status_code == 401


def test_authenticated_chat_filters_authz_and_emits_permission_cards(monkeypatch):
    client, _, logs, _ = _client(monkeypatch)
    token = _login(client, "alice", "User@123")

    with client.stream(
        "POST",
        "/api/ai/chat/stream",
        headers=_auth(token),
        json={"question": "怎么检修？", "session_id": "sess-alice"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = _parse_sse(raw)
    names = [name for name, _ in events]
    assert SSEEvent.PERMISSION_MISSING in names
    assert SSEEvent.FINAL in names

    missing = next(payload for name, payload in events if name == SSEEvent.PERMISSION_MISSING)
    assert any(c.get("unit_id") == "ku-secret-001" for c in missing["cards"])
    assert all(c.get("unit_id") != EXAMPLE_UNIT_ID for c in missing["cards"])

    final = next(payload for name, payload in events if name == SSEEvent.FINAL)
    assert "授权知识" in final["answer"]
    assert EXAMPLE_UNIT_ID in final["authorized_unit_ids"]
    assert "ku-secret-001" not in final["authorized_unit_ids"]
    assert all(r.get("unit_id") != "ku-secret-001" for r in final.get("references") or [])
    assert "机密手册" not in final["answer"]

    deadline = time.time() + 2
    while time.time() < deadline and not logs.list_all():
        time.sleep(0.01)
    entries = logs.list_all()
    assert len(entries) == 1
    entry = entries[0]
    assert entry["user_id"] == "user-alice"
    assert entry["question"] == "怎么检修？"
    assert EXAMPLE_UNIT_ID in entry["authorized_unit_ids"]
    assert "ku-secret-001" in entry["unauthorized_unit_ids"]
    assert EXAMPLE_UNIT_ID in entry["recalled_unit_ids"]
    assert entry["total_tokens"] == 20
    assert entry["response_time_ms"] >= 0


def test_bob_same_question_unauthorized_outcome(monkeypatch):
    client, _, logs, _ = _client(monkeypatch)
    token = _login(client, "bob", "User@123")

    with client.stream(
        "POST",
        "/api/ai/chat/stream",
        headers=_auth(token),
        json={"question": "怎么检修？", "session_id": "sess-bob"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = _parse_sse(raw)
    final = next(payload for name, payload in events if name == SSEEvent.FINAL)
    assert final["authorized_unit_ids"] == []
    assert EXAMPLE_UNIT_ID in [
        c["unit_id"]
        for name, payload in events
        if name == SSEEvent.PERMISSION_MISSING
        for c in payload["cards"]
    ]
    assert "均无访问权限" in final["answer"] or "无访问权限" in final["answer"]

    deadline = time.time() + 2
    while time.time() < deadline and not logs.list_all():
        time.sleep(0.01)
    entry = logs.list_all()[0]
    assert entry["user_id"] == "user-bob"
    assert EXAMPLE_UNIT_ID in entry["unauthorized_unit_ids"]
    assert entry["authorized_unit_ids"] == []


def test_authz_filter_node_only_keeps_authorized_unit_ids():
    knowledge_repo = MemoryKnowledgeRepository()
    knowledge = KnowledgeService(repository=knowledge_repo)
    seed_example_knowledge_unit(knowledge)
    state = {
        "reranked_docs": [
            {
                "unit_id": EXAMPLE_UNIT_ID,
                "title": "示例产品安全手册",
                "content": "ok",
                "source": "local",
            },
            {
                "unit_id": "ku-nope",
                "title": "无权单元",
                "content": "secret",
                "source": "local",
            },
            {
                "title": "网页资料",
                "content": "web",
                "source": "web",
            },
        ],
        "user_id": "user-alice",
        "department_id": "dept-ops",
        "role_ids": ["role-user"],
        "permission_checker": lambda unit_ids: knowledge.check_permissions(
            unit_ids=unit_ids,
            user_id="user-alice",
            department_id="dept-ops",
            role_ids=["role-user"],
        ),
    }
    AuthzFilterNode().process(state)
    kept_ids = [d.get("unit_id") for d in state["reranked_docs"] if d.get("unit_id")]
    assert kept_ids == [EXAMPLE_UNIT_ID]
    assert any(d.get("source") == "web" for d in state["reranked_docs"])
    assert state["unauthorized_unit_ids"] == ["ku-nope"]
    assert state["authorized_unit_ids"] == [EXAMPLE_UNIT_ID]


def test_query_graph_still_has_item_name_confirm_path():
    source = Path(
        "knowledge/processor/query_processor/main_graph.py"
    ).read_text(encoding="utf-8")
    assert "item_name_confirmed_node" in source
    assert "authz_filter_node" in source
    assert "reranker_node" in source
    assert "answer_output_node" in source
    assert 'workflow.add_edge("reranker_node", "authz_filter_node")' in source
    assert 'workflow.add_edge("authz_filter_node", "answer_output_node")' in source
    assert "route_after_item_confirm" in source


def test_authz_filter_node_fail_closed_without_permission_checker():
    state = {
        "reranked_docs": [
            {
                "unit_id": EXAMPLE_UNIT_ID,
                "title": "示例产品安全手册",
                "content": "ok",
                "source": "local",
            },
            {
                "title": "网页资料",
                "content": "web",
                "source": "web",
            },
        ],
        "permission_checker": None,
    }
    AuthzFilterNode().process(state)
    assert all(not d.get("unit_id") for d in state["reranked_docs"])
    assert any(d.get("source") == "web" for d in state["reranked_docs"])
    assert state["authorized_unit_ids"] == []
    assert EXAMPLE_UNIT_ID in state["unauthorized_unit_ids"]
    assert any(c["unit_id"] == EXAMPLE_UNIT_ID for c in state["unauthorized_units"])


def test_chat_history_requires_auth_and_returns_items(monkeypatch):
    client, _, _, history_store = _client(monkeypatch)
    denied = client.get("/api/ai/chat/history/sess-x")
    assert denied.status_code == 401

    history_store["user-alice:sess-x"] = [
        {
            "_id": "1",
            "session_id": "user-alice:sess-x",
            "role": "user",
            "text": "你好",
            "rewritten_query": "你好",
            "item_names": [],
            "ts": 1,
        },
        {
            "_id": "2",
            "session_id": "user-alice:sess-x",
            "role": "assistant",
            "text": "您好",
            "rewritten_query": "",
            "item_names": [],
            "ts": 2,
        },
    ]
    token = _login(client, "alice", "User@123")
    response = client.get("/api/ai/chat/history/sess-x", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "sess-x"
    assert len(body["items"]) >= 2


def test_bob_cannot_read_alice_session_history(monkeypatch):
    client, _, _, history_store = _client(monkeypatch)
    history_store["user-alice:shared-sess"] = [
        {
            "_id": "1",
            "session_id": "user-alice:shared-sess",
            "role": "user",
            "text": "alice 私密问题",
            "rewritten_query": "",
            "item_names": [],
            "ts": 1,
        }
    ]
    bob_token = _login(client, "bob", "User@123")
    response = client.get(
        "/api/ai/chat/history/shared-sess",
        headers=_auth(bob_token),
    )
    assert response.status_code == 200
    assert response.json()["items"] == []

    alice_token = _login(client, "alice", "User@123")
    alice_resp = client.get(
        "/api/ai/chat/history/shared-sess",
        headers=_auth(alice_token),
    )
    assert alice_resp.status_code == 200
    assert len(alice_resp.json()["items"]) == 1
    assert "alice 私密问题" in alice_resp.json()["items"][0]["text"]


def test_graph_failure_emits_sse_final(monkeypatch):
    client, knowledge_service, logs, history_store = _client(monkeypatch)

    def boom(_state: dict) -> dict:
        raise RuntimeError("graph exploded")

    def history_getter(session_id: str, limit: int = 50):
        return list(history_store.get(session_id, [])[-limit:])

    def history_clearer(session_id: str) -> int:
        n = len(history_store.get(session_id, []))
        history_store.pop(session_id, None)
        return n

    chat_service = ChatService(
        knowledge_service=knowledge_service,
        access_logs=logs,
        graph_runner=boom,
        history_getter=history_getter,
        history_clearer=history_clearer,
    )
    client.app.dependency_overrides[ai_router.get_chat_service] = lambda: chat_service

    token = _login(client, "alice", "User@123")
    with client.stream(
        "POST",
        "/api/ai/chat/stream",
        headers=_auth(token),
        json={"question": "怎么检修？", "session_id": "sess-fail"},
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())

    events = _parse_sse(raw)
    assert SSEEvent.FINAL in [name for name, _ in events]
    final = next(payload for name, payload in events if name == SSEEvent.FINAL)
    assert "失败" in final["answer"]
    assert final.get("error")


def test_get_chat_service_does_not_swallow_seed_failures(monkeypatch):
    class BrokenKnowledge:
        def get_unit(self, unit_id: str):
            raise RuntimeError("seed backend down")

        def insert_unit(self, unit):
            raise RuntimeError("seed backend down")

    monkeypatch.setattr(ai_router, "get_knowledge_service", lambda: BrokenKnowledge())
    ai_router.get_chat_service.cache_clear()
    try:
        raised = False
        try:
            ai_router.get_chat_service()
        except RuntimeError as exc:
            raised = True
            assert "seed backend down" in str(exc)
        assert raised
    finally:
        ai_router.get_chat_service.cache_clear()
