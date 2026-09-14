from __future__ import annotations

from functools import lru_cache
from typing import Callable

from fastapi import Depends, Header, HTTPException, status

from knowledge.auth import AuthService, create_seeded_memory_repository
from knowledge.auth.repository import AuthRepository, MongoAuthRepository
from knowledge.auth.schemas import MeResponse
from knowledge.org.service import OrgService


def extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录凭证缺失",
        )
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未登录或登录凭证缺失",
        )
    return token


@lru_cache
def get_shared_repository() -> AuthRepository:
    from knowledge.utils.client.storage_clients import StorageClients

    db = StorageClients.get_mongo_db()
    repo = MongoAuthRepository(db)
    if not repo.list_users():
        seeded = create_seeded_memory_repository()
        for user in seeded.list_users():
            repo.create_user(user)
        for dept in seeded.list_departments():
            repo.upsert_department(dept)
        for role in seeded.list_roles():
            repo.upsert_role(role)
    return repo


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(repository=get_shared_repository())


@lru_cache
def get_org_service() -> OrgService:
    return OrgService(repository=get_shared_repository())


def get_current_user(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    return auth_service.me(extract_bearer(authorization))


def require_permissions(*codes: str) -> Callable[..., MeResponse]:
    def _checker(user: MeResponse = Depends(get_current_user)) -> MeResponse:
        missing = [code for code in codes if code not in user.permissions]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无操作权限",
            )
        return user

    return _checker
