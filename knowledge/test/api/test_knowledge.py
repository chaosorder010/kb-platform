from fastapi.testclient import TestClient

from knowledge.api import app_main, auth_router, deps, knowledge_router
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService
from knowledge.units.repository import MemoryKnowledgeRepository
from knowledge.units.service import KnowledgeService
from io import BytesIO

from docx import Document

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
    knowledge_service = KnowledgeService(repository=knowledge_repo)

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


def test_import_requires_auth(monkeypatch):
    client, _ = _client(monkeypatch)
    response = client.post(
        "/api/knowledge/import",
        files=[("files", ("a.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 401


def test_import_requires_create_permission(monkeypatch):
    client, _ = _client(monkeypatch)
    token = _login(client, "alice", "User@123")
    response = client.post(
        "/api/knowledge/import",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("a.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 403


def test_import_pdf_md_txt_creates_units_and_tasks(monkeypatch):
    client, service = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")

    files = [
        ("files", ("手册.pdf", b"%PDF-1.4 demo", "application/pdf")),
        ("files", ("说明.md", "# 标题\n内容".encode("utf-8"), "text/markdown")),
        ("files", ("备注.txt", "纯文本内容".encode("utf-8"), "text/plain")),
    ]
    response = client.post(
        "/api/knowledge/import",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tasks"]) == 3
    for task in body["tasks"]:
        assert task["task_id"]
        assert task["unit_id"]
        assert task["filename"]

    units = service.list_units()
    assert len(units["items"]) == 3
    for item in units["items"]:
        assert item["data_permissions"] == []
        assert item["permission_summary"] == "无数据权限"
        assert item["file_type"] in {"pdf", "md", "txt"}


def test_import_rejects_unsupported_format(monkeypatch):
    client, _ = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")
    response = client.post(
        "/api/knowledge/import",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("a.xlsx", b"xx", "application/octet-stream"))],
    )
    assert response.status_code == 400
    assert "不支持" in response.json()["detail"]


def _docx_bytes(paragraphs: list[str]) -> bytes:
    document = Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_import_docx_creates_unit_and_runs_pipeline(monkeypatch):
    client, service = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")
    content = _docx_bytes(["Word 导入段落一。", "Word 导入段落二。"])

    response = client.post(
        "/api/knowledge/import",
        headers={"Authorization": f"Bearer {token}"},
        files=[
            (
                "files",
                (
                    "操作手册.docx",
                    content,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            )
        ],
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["tasks"]) == 1
    task = body["tasks"][0]
    assert task["unit_id"].startswith("ku-")
    assert task["filename"] == "操作手册.docx"

    written = service.run_import_task_sync(task["task_id"])
    assert written
    assert all(chunk.get("unit_id") == task["unit_id"] for chunk in written)

    units = client.get(
        "/api/knowledge/units",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "操作手册"},
    )
    assert units.status_code == 200
    items = units.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == task["unit_id"]
    assert items[0]["file_type"] == "docx"
    assert items[0]["status"] == "published"
    assert "Word 导入" in items[0]["content"]

    status = client.get(
        f"/api/knowledge/import/tasks/{task['task_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status.status_code == 200
    assert status.json()["status"] == "completed"
    assert status.json()["unit_id"] == task["unit_id"]


def test_import_corrupt_docx_returns_clear_error(monkeypatch):
    client, service = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")
    tasks = service.import_files(
        files=[("坏文件.docx", b"not-a-real-docx")],
        creator_id="user-kbadmin",
        creator_name="知识管理员",
    )
    task = tasks[0]
    try:
        service.run_import_task_sync(task["task_id"])
        raise AssertionError("expected corrupt docx to fail")
    except ValueError as exc:
        assert "Word" in str(exc) or "docx" in str(exc).lower() or "解析" in str(exc)

    status = client.get(
        f"/api/knowledge/import/tasks/{task['task_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "failed"
    assert body["error"]

    units = service.list_units(q="坏文件")
    assert units["items"][0]["status"] == "failed"


def test_import_legacy_doc_returns_clear_error(monkeypatch):
    client, service = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")
    tasks = service.import_files(
        files=[("旧稿.doc", b"\xd0\xcf\x11\xe0")],
        creator_id="user-kbadmin",
        creator_name="知识管理员",
    )
    task = tasks[0]
    try:
        service.run_import_task_sync(task["task_id"])
        raise AssertionError("expected legacy .doc to fail")
    except ValueError as exc:
        assert ".doc" in str(exc) or "docx" in str(exc)

    status = client.get(
        f"/api/knowledge/import/tasks/{task['task_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status.json()["status"] == "failed"
    assert status.json()["error"]


def test_import_task_status_progress(monkeypatch):
    client, service = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")
    response = client.post(
        "/api/knowledge/import",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("备注.txt", "纯文本内容".encode("utf-8"), "text/plain"))],
    )
    task_id = response.json()["tasks"][0]["task_id"]
    unit_id = response.json()["tasks"][0]["unit_id"]

    service.run_import_task_sync(task_id)

    status = client.get(
        f"/api/knowledge/import/tasks/{task_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "completed"
    assert body["unit_id"] == unit_id
    assert body["progress"] == 100
    assert isinstance(body["done_list"], list)
    assert len(body["done_list"]) > 0


def test_list_units_search_and_filter(monkeypatch):
    client, service = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")

    service.create_unit_for_file(
        filename="A手册.pdf",
        content=b"%PDF",
        creator_id="user-kbadmin",
        creator_name="知识管理员",
        category="产品手册",
    )
    service.create_unit_for_file(
        filename="B说明.md",
        content=b"# B",
        creator_id="user-kbadmin",
        creator_name="知识管理员",
        category="运维",
        status="published",
    )

    response = client.get(
        "/api/knowledge/units",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "手册", "category": "产品手册"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    item = items[0]
    assert item["unit_code"]
    assert item["title"]
    assert item["category"] == "产品手册"
    assert item["file_type"] == "pdf"
    assert "permission_summary" in item
    assert item["creator_name"]
    assert item["created_at"]
    assert item["status"]


def test_list_units_requires_view_permission(monkeypatch):
    client, _ = _client(monkeypatch)
    response = client.get("/api/knowledge/units")
    assert response.status_code == 401


def test_chunks_carry_unit_id(monkeypatch):
    client, service = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")
    response = client.post(
        "/api/knowledge/import",
        headers={"Authorization": f"Bearer {token}"},
        files=[("files", ("备注.txt", "切片内容一二三".encode("utf-8"), "text/plain"))],
    )
    task_id = response.json()["tasks"][0]["task_id"]
    unit_id = response.json()["tasks"][0]["unit_id"]
    written = service.run_import_task_sync(task_id)
    assert written
    assert all(chunk.get("unit_id") == unit_id for chunk in written)
