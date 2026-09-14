from fastapi.testclient import TestClient

from knowledge.api import app_main, auth_router, deps, knowledge_router
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService
from knowledge.units.repository import MemoryKnowledgeRepository
from knowledge.units.chunk_writer import MemoryChunkWriter
from knowledge.units.service import KnowledgeService, light_import_pipeline


def _seeded_auth() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )


def _client(monkeypatch) -> tuple[TestClient, KnowledgeService]:
    auth_repo = _seeded_auth()
    auth_service = AuthService(repository=auth_repo)
    knowledge_repo = MemoryKnowledgeRepository()
    knowledge_service = KnowledgeService(
        repository=knowledge_repo,
        chunk_writer=MemoryChunkWriter(),
        pipeline=light_import_pipeline,
    )

    monkeypatch.setattr(
        app_main,
        "load_domain_routers",
        lambda: [auth_router.router, knowledge_router.router],
    )
    app = app_main.create_app()
    app.dependency_overrides[deps.get_auth_service] = lambda: auth_service
    app.dependency_overrides[knowledge_router.get_knowledge_service] = (
        lambda: knowledge_service
    )
    return TestClient(app), knowledge_service


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_unit(service: KnowledgeService, **kwargs) -> dict:
    defaults = {
        "filename": "guide.md",
        "content": b"# hello\n\nbody",
        "creator_id": "user-kbadmin",
        "creator_name": "知识管理员",
        "status": "draft",
    }
    defaults.update(kwargs)
    unit = service.create_unit_for_file(**defaults)
    service._repo.update_unit(
        unit["id"],
        {"content": defaults["content"].decode("utf-8"), "status": defaults["status"]},
    )
    return service._repo.get_unit(unit["id"])


def test_put_unit_edits_title_content_tags_and_attachment(monkeypatch):
    client, service = _client(monkeypatch)
    unit = _create_unit(service)
    token = _login(client, "kbadmin", "Kb@123456")

    response = client.put(
        f"/api/knowledge/units/{unit['id']}",
        headers=_auth(token),
        json={
            "title": "新标题",
            "content": "更新后的正文",
            "tags": ["运维", "手册"],
            "status": "published",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "新标题"
    assert body["content"] == "更新后的正文"
    assert body["tags"] == ["运维", "手册"]
    assert body["status"] == "published"

    upload = client.post(
        f"/api/knowledge/units/{unit['id']}/attachments",
        headers=_auth(token),
        files={"file": ("note.txt", b"attachment-bytes", "text/plain")},
    )
    assert upload.status_code == 200
    att = upload.json()
    assert att["filename"] == "note.txt"
    assert att["object_key"]
    assert att["size"] == len(b"attachment-bytes")

    detail = client.get(
        f"/api/knowledge/units/{unit['id']}",
        headers=_auth(token),
    )
    assert detail.status_code == 200
    assert len(detail.json()["attachments"]) == 1
    assert detail.json()["attachments"][0]["filename"] == "note.txt"


def test_save_creates_version_snapshots_and_status_transitions(monkeypatch):
    client, service = _client(monkeypatch)
    unit = _create_unit(service, status="draft")
    token = _login(client, "kbadmin", "Kb@123456")

    first = client.put(
        f"/api/knowledge/units/{unit['id']}",
        headers=_auth(token),
        json={"title": "v1", "content": "c1", "status": "published"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "published"

    second = client.put(
        f"/api/knowledge/units/{unit['id']}",
        headers=_auth(token),
        json={"title": "v2", "content": "c2", "status": "disabled"},
    )
    assert second.status_code == 200
    assert second.json()["status"] == "disabled"

    versions = client.get(
        f"/api/knowledge/units/{unit['id']}/versions",
        headers=_auth(token),
    )
    assert versions.status_code == 200
    items = versions.json()["items"]
    assert len(items) >= 2
    assert items[0]["version"] >= items[1]["version"]
    assert {v["title"] for v in items} >= {"v1", "v2"}
    assert all("editor_id" in v and "created_at" in v for v in items)


def test_invalid_status_transition_rejected(monkeypatch):
    client, service = _client(monkeypatch)
    unit = _create_unit(service, status="processing")
    token = _login(client, "kbadmin", "Kb@123456")

    response = client.put(
        f"/api/knowledge/units/{unit['id']}",
        headers=_auth(token),
        json={"status": "published"},
    )
    assert response.status_code == 400


def test_permissions_mixed_or_and_check_permissions(monkeypatch):
    client, service = _client(monkeypatch)
    unit = _create_unit(service)
    token = _login(client, "kbadmin", "Kb@123456")

    denied = client.post(
        "/api/knowledge/check-permissions",
        headers=_auth(token),
        json={
            "unit_ids": [unit["id"]],
            "user_id": "user-alice",
            "department_id": "dept-ops",
            "role_ids": ["role-user"],
        },
    )
    assert denied.status_code == 200
    assert denied.json()["results"][0]["authorized"] is False

    save = client.post(
        f"/api/knowledge/units/{unit['id']}/permissions",
        headers=_auth(token),
        json={
            "permissions": [
                {"type": "department", "id": "dept-ops"},
                {"type": "role", "id": "role-kb-admin"},
                {"type": "user", "id": "user-bob"},
            ]
        },
    )
    assert save.status_code == 200
    assert save.json()["permission_summary"] != "无数据权限"

    alice_ok = client.post(
        "/api/knowledge/check-permissions",
        headers=_auth(token),
        json={
            "unit_ids": [unit["id"]],
            "user_id": "user-alice",
            "department_id": "dept-ops",
            "role_ids": ["role-user"],
        },
    )
    assert alice_ok.status_code == 200
    assert alice_ok.json()["results"][0]["authorized"] is True

    bob_ok = client.post(
        "/api/knowledge/check-permissions",
        headers=_auth(token),
        json={
            "unit_ids": [unit["id"]],
            "user_id": "user-bob",
            "department_id": "dept-hq",
            "role_ids": ["role-user"],
        },
    )
    assert bob_ok.status_code == 200
    assert bob_ok.json()["results"][0]["authorized"] is True

    stranger = client.post(
        "/api/knowledge/check-permissions",
        headers=_auth(token),
        json={
            "unit_ids": [unit["id"]],
            "user_id": "user-stranger",
            "department_id": "dept-other",
            "role_ids": ["role-other"],
        },
    )
    assert stranger.status_code == 200
    assert stranger.json()["results"][0]["authorized"] is False

    global_perm = client.post(
        f"/api/knowledge/units/{unit['id']}/permissions",
        headers=_auth(token),
        json={"permissions": [{"type": "global", "id": "*"}]},
    )
    assert global_perm.status_code == 200
    anyone = client.post(
        "/api/knowledge/check-permissions",
        headers=_auth(token),
        json={
            "unit_ids": [unit["id"]],
            "user_id": "user-stranger",
            "department_id": "dept-other",
            "role_ids": ["role-other"],
        },
    )
    assert anyone.json()["results"][0]["authorized"] is True


def test_default_unit_has_no_data_permission(monkeypatch):
    client, service = _client(monkeypatch)
    unit = _create_unit(service)
    token = _login(client, "kbadmin", "Kb@123456")

    listed = client.get("/api/knowledge/units", headers=_auth(token))
    assert listed.status_code == 200
    item = next(i for i in listed.json()["items"] if i["id"] == unit["id"])
    assert item["permission_summary"] == "无数据权限"
    assert item["data_permissions"] == []


def test_batch_delete_units(monkeypatch):
    client, service = _client(monkeypatch)
    u1 = _create_unit(service, filename="a.md")
    u2 = _create_unit(service, filename="b.md")
    token = _login(client, "kbadmin", "Kb@123456")

    response = client.request(
        "DELETE",
        "/api/knowledge/units",
        headers=_auth(token),
        json={"ids": [u1["id"], u2["id"]]},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == 2

    listed = client.get("/api/knowledge/units", headers=_auth(token))
    ids = {i["id"] for i in listed.json()["items"]}
    assert u1["id"] not in ids
    assert u2["id"] not in ids


def test_edit_requires_update_permission(monkeypatch):
    client, service = _client(monkeypatch)
    unit = _create_unit(service)
    token = _login(client, "alice", "User@123")

    response = client.put(
        f"/api/knowledge/units/{unit['id']}",
        headers=_auth(token),
        json={"title": "hack"},
    )
    assert response.status_code == 403
