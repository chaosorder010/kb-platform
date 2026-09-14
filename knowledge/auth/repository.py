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

    def list_users(self) -> list[dict]: ...

    def list_departments(self) -> list[dict]: ...

    def list_roles(self) -> list[dict]: ...

    def get_role(self, role_id: str) -> dict | None: ...

    def set_role_permissions(self, role_id: str, permissions: list[str]) -> dict | None: ...

    def create_user(self, user: dict) -> dict: ...

    def update_user(self, user_id: str, updates: dict) -> dict | None: ...

    def update_department(self, department_id: str, updates: dict) -> dict | None: ...

    def upsert_department(self, department: dict) -> dict: ...

    def upsert_role(self, role: dict) -> dict: ...


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

    def list_users(self) -> list[dict]:
        return [deepcopy(u) for u in self._users_by_id.values()]

    def list_departments(self) -> list[dict]:
        return [deepcopy(d) for d in self._departments.values()]

    def list_roles(self) -> list[dict]:
        return [deepcopy(r) for r in self._roles.values()]

    def get_role(self, role_id: str) -> dict | None:
        role = self._roles.get(role_id)
        return deepcopy(role) if role else None

    def set_role_permissions(self, role_id: str, permissions: list[str]) -> dict | None:
        role = self._roles.get(role_id)
        if role is None:
            return None
        role["permissions"] = list(permissions)
        return deepcopy(role)

    def create_user(self, user: dict) -> dict:
        self.upsert_user(user)
        return deepcopy(user)

    def update_user(self, user_id: str, updates: dict) -> dict | None:
        user = self._users_by_id.get(user_id)
        if user is None:
            return None
        old_username = user["username"]
        user.update(updates)
        if user["username"] != old_username:
            self._users.pop(old_username, None)
        self._users[user["username"]] = user
        self._users_by_id[user_id] = user
        return deepcopy(user)

    def update_department(self, department_id: str, updates: dict) -> dict | None:
        dept = self._departments.get(department_id)
        if dept is None:
            return None
        dept.update(updates)
        self._departments[department_id] = dept
        return deepcopy(dept)

    def upsert_department(self, department: dict) -> dict:
        stored = deepcopy(department)
        self._departments[stored["id"]] = stored
        return deepcopy(stored)

    def upsert_role(self, role: dict) -> dict:
        stored = deepcopy(role)
        self._roles[stored["id"]] = stored
        return deepcopy(stored)


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

    def list_users(self) -> list[dict]:
        return list(self._db.users.find({}, {"_id": 0}))

    def list_departments(self) -> list[dict]:
        return list(self._db.departments.find({}, {"_id": 0}))

    def list_roles(self) -> list[dict]:
        return list(self._db.roles.find({}, {"_id": 0}))

    def get_role(self, role_id: str) -> dict | None:
        return self._db.roles.find_one({"id": role_id}, {"_id": 0})

    def set_role_permissions(self, role_id: str, permissions: list[str]) -> dict | None:
        role = self.get_role(role_id)
        if role is None:
            return None
        self._db.role_permissions.delete_many({"role_id": role_id})
        if permissions:
            self._db.role_permissions.insert_many(
                [{"role_id": role_id, "permission_code": code, "permission_type": "action"} for code in permissions]
            )
        self._db.roles.update_one({"id": role_id}, {"$set": {"permissions": list(permissions)}})
        return self.get_role(role_id)

    def create_user(self, user: dict) -> dict:
        self._db.users.update_one({"id": user["id"]}, {"$set": user}, upsert=True)
        return dict(user)

    def update_user(self, user_id: str, updates: dict) -> dict | None:
        self._db.users.update_one({"id": user_id}, {"$set": updates})
        return self.get_user_by_id(user_id)

    def update_department(self, department_id: str, updates: dict) -> dict | None:
        self._db.departments.update_one({"id": department_id}, {"$set": updates})
        return self.get_department(department_id)

    def upsert_department(self, department: dict) -> dict:
        self._db.departments.update_one({"id": department["id"]}, {"$set": department}, upsert=True)
        return dict(department)

    def upsert_role(self, role: dict) -> dict:
        self._db.roles.update_one({"id": role["id"]}, {"$set": role}, upsert=True)
        permissions = list(role.get("permissions") or [])
        self._db.role_permissions.delete_many({"role_id": role["id"]})
        if permissions:
            self._db.role_permissions.insert_many(
                [{"role_id": role["id"], "permission_code": code, "permission_type": "action"} for code in permissions]
            )
        return dict(role)


def create_seeded_memory_repository() -> MemoryAuthRepository:
    return MemoryAuthRepository(
        users=build_seed_users(),
        departments=list(SEED_DEPARTMENTS),
        roles=list(SEED_ROLES),
    )
