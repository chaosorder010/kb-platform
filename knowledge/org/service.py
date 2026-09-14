from __future__ import annotations

import uuid

from fastapi import HTTPException, status

from knowledge.auth.password import hash_password
from knowledge.auth.repository import AuthRepository
from knowledge.org.permissions import PERMISSION_TREE
from knowledge.org.schemas import (
    DepartmentUpdateRequest,
    DepartmentInfo,
    DepartmentNode,
    OrgRole,
    OrgUser,
    PermissionNode,
    RoleInfo,
    UserBrief,
    UserCreateRequest,
    UserUpdateRequest,
)


class OrgService:
    def __init__(self, repository: AuthRepository) -> None:
        self._repo = repository

    def list_department_tree(self) -> list[DepartmentNode]:
        departments = self._repo.list_departments()
        users = self._repo.list_users()
        by_parent: dict[str | None, list[dict]] = {}
        for dept in departments:
            by_parent.setdefault(dept.get("parent_id"), []).append(dept)
        for items in by_parent.values():
            items.sort(key=lambda d: (d.get("sort_order", 0), d.get("name", "")))

        users_by_id = {u["id"]: u for u in users}
        users_by_dept: dict[str, list[dict]] = {}
        for user in users:
            users_by_dept.setdefault(user.get("department_id", ""), []).append(user)

        def to_brief(user: dict | None) -> UserBrief | None:
            if user is None:
                return None
            return UserBrief(
                id=user["id"],
                username=user["username"],
                display_name=user["display_name"],
            )

        def build(node: dict) -> DepartmentNode:
            leader = users_by_id.get(node.get("leader_id") or "")
            members = [
                to_brief(u)
                for u in users_by_dept.get(node["id"], [])
                if to_brief(u) is not None
            ]
            children = [build(child) for child in by_parent.get(node["id"], [])]
            return DepartmentNode(
                id=node["id"],
                name=node["name"],
                parent_id=node.get("parent_id"),
                sort_order=node.get("sort_order", 0),
                leader=to_brief(leader),
                members=members,
                children=children,
            )

        roots = by_parent.get(None, [])
        return [build(root) for root in roots]

    def update_department(self, department_id: str, body: DepartmentUpdateRequest) -> DepartmentNode:
        dept = self._repo.get_department(department_id)
        if dept is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
        updates: dict = {}
        if body.leader_id is not None:
            if body.leader_id and self._repo.get_user_by_id(body.leader_id) is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="负责人不存在")
            updates["leader_id"] = body.leader_id
        if updates:
            self._repo.update_department(department_id, updates)
        if body.member_ids is not None:
            wanted = set(body.member_ids)
            for uid in wanted:
                user = self._repo.get_user_by_id(uid)
                if user is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"成员不存在: {uid}",
                    )
            fallback = dept.get("parent_id") or ""
            for user in self._repo.list_users():
                uid = user["id"]
                if uid in wanted:
                    if user.get("department_id") != department_id:
                        self._repo.update_user(uid, {"department_id": department_id})
                elif user.get("department_id") == department_id and fallback:
                    self._repo.update_user(uid, {"department_id": fallback})
        tree = self.list_department_tree()

        def find(nodes: list[DepartmentNode]) -> DepartmentNode | None:
            for node in nodes:
                if node.id == department_id:
                    return node
                found = find(node.children or [])
                if found:
                    return found
            return None

        node = find(tree)
        if node is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="部门不存在")
        return node


    def list_users(self) -> list[OrgUser]:
        return [self._to_org_user(user) for user in self._repo.list_users()]

    def create_user(self, body: UserCreateRequest) -> OrgUser:
        if self._repo.get_user_by_username(body.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在",
            )
        if not self._repo.get_department(body.department_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="部门不存在",
            )
        roles = self._repo.get_roles_by_ids(body.role_ids)
        if len(roles) != len(set(body.role_ids)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="角色不存在",
            )
        user = {
            "id": f"user-{uuid.uuid4().hex[:8]}",
            "username": body.username,
            "password_hash": hash_password(body.password),
            "display_name": body.display_name,
            "department_id": body.department_id,
            "status": body.status or "active",
            "role_ids": list(body.role_ids),
        }
        created = self._repo.create_user(user)
        return self._to_org_user(created)

    def update_user(self, user_id: str, body: UserUpdateRequest) -> OrgUser:
        existing = self._repo.get_user_by_id(user_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )
        updates: dict = {}
        if body.display_name is not None:
            updates["display_name"] = body.display_name
        if body.department_id is not None:
            if not self._repo.get_department(body.department_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="部门不存在",
                )
            updates["department_id"] = body.department_id
        if body.role_ids is not None:
            roles = self._repo.get_roles_by_ids(body.role_ids)
            if len(roles) != len(set(body.role_ids)):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="角色不存在",
                )
            updates["role_ids"] = list(body.role_ids)
        if body.status is not None:
            updates["status"] = body.status
        if body.password:
            updates["password_hash"] = hash_password(body.password)
        updated = self._repo.update_user(user_id, updates)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在",
            )
        return self._to_org_user(updated)

    def list_roles(self) -> list[OrgRole]:
        return [
            OrgRole(
                id=role["id"],
                role_name=role["role_name"],
                role_code=role["role_code"],
                description=role.get("description", ""),
                permissions=list(role.get("permissions", [])),
            )
            for role in self._repo.list_roles()
        ]

    def set_role_permissions(self, role_id: str, permissions: list[str]) -> OrgRole:
        role = self._repo.set_role_permissions(role_id, permissions)
        if role is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="角色不存在",
            )
        return OrgRole(
            id=role["id"],
            role_name=role["role_name"],
            role_code=role["role_code"],
            description=role.get("description", ""),
            permissions=list(role.get("permissions", [])),
        )

    def permission_tree(self) -> list[PermissionNode]:
        return [PermissionNode.model_validate(node) for node in PERMISSION_TREE]

    def require_permission(self, permissions: list[str], code: str) -> None:
        if code not in permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无操作权限",
            )

    def require_any_permission(self, permissions: list[str], codes: list[str]) -> None:
        if not any(code in permissions for code in codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无操作权限",
            )

    def _to_org_user(self, user: dict) -> OrgUser:
        dept = self._repo.get_department(user.get("department_id", "")) or {
            "id": "",
            "name": "",
        }
        roles = [
            RoleInfo(
                id=role["id"],
                role_name=role["role_name"],
                role_code=role["role_code"],
            )
            for role in self._repo.get_roles_by_ids(user.get("role_ids", []))
        ]
        return OrgUser(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            status=user["status"],
            department=DepartmentInfo(id=dept["id"], name=dept["name"]),
            roles=roles,
        )
