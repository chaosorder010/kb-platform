from fastapi.testclient import TestClient

from knowledge.api import app_main, auth_router, org_router
from knowledge.api.deps import get_auth_service, get_org_service
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService
from knowledge.org.service import OrgService


def _seeded_repo() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )


def _client(monkeypatch, repo: MemoryAuthRepository | None = None) -> TestClient:
    store = repo or _seeded_repo()
    auth_service = AuthService(repository=store)
    org_service = OrgService(repository=store)

    monkeypatch.setattr(
        app_main,
        "load_domain_routers",
        lambda: [auth_router.router, org_router.router],
    )
    app = app_main.create_app()
    app.dependency_overrides[get_auth_service] = lambda: auth_service
    app.dependency_overrides[get_org_service] = lambda: org_service
    return TestClient(app)


def _login(client: TestClient, username: str = "admin", password: str = "Admin@123") -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_departments_requires_auth(monkeypatch):
    client = _client(monkeypatch)
    response = client.get("/api/org/departments")
    assert response.status_code == 401


def test_departments_tree_for_admin(monkeypatch):
    client = _client(monkeypatch)
    token = _login(client)
    response = client.get("/api/org/departments", headers=_auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    root = body[0]
    assert root["name"] == "总部"
    assert "children" in root
    assert any(c["name"] == "运营部" for c in root["children"])
    assert root["leader"]["username"] == "admin"
    ops = next(c for c in root["children"] if c["name"] == "运营部")
    member_names = {m["username"] for m in ops["members"]}
    assert "alice" in member_names
    assert "kbadmin" in member_names


def test_list_users_requires_permission(monkeypatch):
    client = _client(monkeypatch)
    token = _login(client, "alice", "User@123")
    response = client.get("/api/org/users", headers=_auth_header(token))
    assert response.status_code == 403


def test_list_and_create_user_as_admin(monkeypatch):
    client = _client(monkeypatch)
    token = _login(client)

    listed = client.get("/api/org/users", headers=_auth_header(token))
    assert listed.status_code == 200
    assert any(u["username"] == "admin" for u in listed.json())

    created = client.post(
        "/api/org/users",
        headers=_auth_header(token),
        json={
            "username": "carol",
            "password": "Carol@123",
            "display_name": "Carol",
            "department_id": "dept-ops",
            "role_ids": ["role-user"],
            "status": "active",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["username"] == "carol"
    assert body["department"]["id"] == "dept-ops"
    assert any(r["role_code"] == "user" for r in body["roles"])

    login_new = client.post(
        "/api/auth/login",
        json={"username": "carol", "password": "Carol@123"},
    )
    assert login_new.status_code == 200


def test_update_user_reset_password_and_disable(monkeypatch):
    client = _client(monkeypatch)
    token = _login(client)

    updated = client.put(
        "/api/org/users/user-alice",
        headers=_auth_header(token),
        json={
            "display_name": "Alice Updated",
            "department_id": "dept-ops",
            "role_ids": ["role-user"],
            "status": "disabled",
            "password": "NewPass@123",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["display_name"] == "Alice Updated"
    assert body["status"] == "disabled"

    blocked = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "NewPass@123"},
    )
    assert blocked.status_code in (401, 403)

    enabled = client.put(
        "/api/org/users/user-alice",
        headers=_auth_header(token),
        json={"status": "active"},
    )
    assert enabled.status_code == 200
    ok = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "NewPass@123"},
    )
    assert ok.status_code == 200


def test_roles_list_and_update_permissions(monkeypatch):
    client = _client(monkeypatch)
    token = _login(client)

    roles = client.get("/api/org/roles", headers=_auth_header(token))
    assert roles.status_code == 200
    role_list = roles.json()
    assert any(r["role_code"] == "system_admin" for r in role_list)
    user_role = next(r for r in role_list if r["role_code"] == "user")
    assert "ai:access" in user_role["permissions"]

    tree = client.get("/api/org/permissions/tree", headers=_auth_header(token))
    assert tree.status_code == 200
    assert isinstance(tree.json(), list)
    assert any(n["code"].startswith("menu:") for n in tree.json())

    updated = client.post(
        f"/api/org/roles/{user_role['id']}/permissions",
        headers=_auth_header(token),
        json={"permissions": ["menu:ai", "ai:access", "menu:dashboard", "dashboard:view"]},
    )
    assert updated.status_code == 200
    assert "dashboard:view" in updated.json()["permissions"]

    alice_login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "User@123"},
    )
    assert alice_login.status_code == 200
    perms = alice_login.json()["permissions"]
    assert "dashboard:view" in perms
    assert "menu:dashboard" in perms


def test_kbadmin_cannot_manage_users(monkeypatch):
    client = _client(monkeypatch)
    token = _login(client, "kbadmin", "Kb@123456")
    response = client.post(
        "/api/org/users",
        headers=_auth_header(token),
        json={
            "username": "dave",
            "password": "Dave@123",
            "display_name": "Dave",
            "department_id": "dept-ops",
            "role_ids": ["role-user"],
        },
    )
    assert response.status_code == 403


def test_update_department_leader_and_members(monkeypatch):
    client = _client(monkeypatch)
    token = _login(client)
    users = client.get("/api/org/users", headers=_auth_header(token)).json()
    alice = next(u for u in users if u["username"] == "alice")
    bob = next(u for u in users if u["username"] == "bob")
    response = client.put(
        "/api/org/departments/dept-ops",
        headers=_auth_header(token),
        json={"leader_id": bob["id"], "member_ids": [alice["id"], bob["id"]]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["leader"]["username"] == "bob"
    member_names = {m["username"] for m in body["members"]}
    assert member_names == {"alice", "bob"}
