from __future__ import annotations

from copy import deepcopy
from typing import Protocol, runtime_checkable

from knowledge.auth.seed import SEED_DEPARTMENTS, SEED_ROLES, build_seed_users


@runtime_checkable
class AuthRepository(Protocol):
    def get_user_by_username(self, username: str) -> dict | None: ...

    def get_user_by_id(self, user_id: str) -> dict | None: ...

    def get_department(self, department_id: str) -> dict | None: ...

    def get_roles_by_ids(self, role_ids: list[str]) -> list[dict]: ...

    def get_permissions_for_roles(self, role_ids: list[str]) -> list[str]: ...


class MemoryAuthRepository:
    def __init__(
        self,
        users: list[dict] | None = None,
        departments: list[dict] | None = None,
        roles: list[dict] | None = None,
    ) -> None:
        self._users = {u["username"]: deepcopy(u) for u in (users or [])}
        self._users_by_id = {u["id"]: self._users[u["username"]] for u in self._users.values()}
        self._departments = {d["id"]: deepcopy(d) for d in (departments or [])}
        self._roles = {r["id"]: deepcopy(r) for r in (roles or [])}

    def upsert_user(self, user: dict) -> None:
        stored = deepcopy(user)
        self._users[stored["username"]] = stored
        self._users_by_id[stored["id"]] = stored

    def get_user_by_username(self, username: str) -> dict | None:
        user = self._users.get(username)
        return deepcopy(user) if user else None

    def get_user_by_id(self, user_id: str) -> dict | None:
        user = self._users_by_id.get(user_id)
        return deepcopy(user) if user else None

    def get_department(self, department_id: str) -> dict | None:
        dept = self._departments.get(department_id)
        return deepcopy(dept) if dept else None

    def get_roles_by_ids(self, role_ids: list[str]) -> list[dict]:
        return [deepcopy(self._roles[rid]) for rid in role_ids if rid in self._roles]

    def get_permissions_for_roles(self, role_ids: list[str]) -> list[str]:
        codes: list[str] = []
        seen: set[str] = set()
        for role in self.get_roles_by_ids(role_ids):
            for code in role.get("permissions", []):
                if code not in seen:
                    seen.add(code)
                    codes.append(code)
        return codes


class MongoAuthRepository:
    def __init__(self, db) -> None:
        self._db = db

    def get_user_by_username(self, username: str) -> dict | None:
        return self._db.users.find_one({"username": username}, {"_id": 0})

    def get_user_by_id(self, user_id: str) -> dict | None:
        return self._db.users.find_one({"id": user_id}, {"_id": 0})

    def get_department(self, department_id: str) -> dict | None:
        return self._db.departments.find_one({"id": department_id}, {"_id": 0})

    def get_roles_by_ids(self, role_ids: list[str]) -> list[dict]:
        if not role_ids:
            return []
        return list(self._db.roles.find({"id": {"$in": role_ids}}, {"_id": 0}))

    def get_permissions_for_roles(self, role_ids: list[str]) -> list[str]:
        if not role_ids:
            return []
        rows = self._db.role_permissions.find({"role_id": {"$in": role_ids}}, {"_id": 0})
        codes: list[str] = []
        seen: set[str] = set()
        for row in rows:
            code = row.get("permission_code")
            if code and code not in seen:
                seen.add(code)
                codes.append(code)
        if codes:
            return codes
        roles = self.get_roles_by_ids(role_ids)
        for role in roles:
            for code in role.get("permissions", []):
                if code not in seen:
                    seen.add(code)
                    codes.append(code)
        return codes


def create_seeded_memory_repository() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )
