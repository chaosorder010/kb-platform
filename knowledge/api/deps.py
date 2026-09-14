from __future__ import annotations

from functools import lru_cache

from knowledge.auth import AuthService, create_seeded_memory_repository
from knowledge.auth.repository import MemoryAuthRepository
from knowledge.org.service import OrgService


@lru_cache
def get_shared_repository() -> MemoryAuthRepository:
    return create_seeded_memory_repository()


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(repository=get_shared_repository())


@lru_cache
def get_org_service() -> OrgService:
    return OrgService(repository=get_shared_repository())
