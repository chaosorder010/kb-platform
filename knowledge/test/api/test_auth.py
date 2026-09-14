from fastapi.testclient import TestClient

from knowledge.api import app_main, auth_router
from knowledge.auth.password import hash_password
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users
from knowledge.auth.service import AuthService


def _seeded_repo() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )


def _client(monkeypatch, repo: MemoryAuthRepository | None = None) -> TestClient:
    store = repo or _seeded_repo()
    service = AuthService(repository=store)

    monkeypatch.setattr(app_main, "load_domain_routers", lambda: [auth_router.router])
    app = app_main.create_app()
    app.dependency_overrides[auth_router.get_auth_service] = lambda: service
    return TestClient(app)


def test_login_success_returns_token_user_info_permissions(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin@123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["user_info"]["username"] == "admin"
    assert body["user_info"]["display_name"]
    assert body["user_info"]["department"]["name"]
    assert any(r["role_code"] == "system_admin" for r in body["user_info"]["roles"])
    assert isinstance(body["permissions"], list)
    assert len(body["permissions"]) > 0


def test_login_wrong_password_returns_401(monkeypatch):
    client = _client(monkeypatch)

    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "密码" in response.json()["detail"] or "凭证" in response.json()["detail"]


def test_login_disabled_user_returns_clear_failure(monkeypatch):
    repo = _seeded_repo()
    bob = repo.get_user_by_username("bob")
    assert bob is not None
    bob["status"] = "disabled"
    bob["password_hash"] = hash_password("User@123")
    repo.upsert_user(bob)
    client = _client(monkeypatch, repo)

    response = client.post(
        "/api/auth/login",
        json={"username": "bob", "password": "User@123"},
    )

    assert response.status_code in (401, 403)
    detail = response.json()["detail"]
    assert "停用" in detail or "禁用" in detail


def test_me_without_token_returns_401(monkeypatch):
    client = _client(monkeypatch)

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_me_with_valid_token_returns_identity_department_roles(monkeypatch):
    client = _client(monkeypatch)
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "User@123"},
    )
    token = login.json()["access_token"]

    response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert body["display_name"]
    assert body["department"]["name"]
    assert any(r["role_code"] == "user" for r in body["roles"])
