from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PermissionNode(BaseModel):
    code: str
    name: str
    children: list[PermissionNode] = Field(default_factory=list)


class UserBrief(BaseModel):
    id: str
    username: str
    display_name: str


class DepartmentNode(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    sort_order: int = 0
    leader: UserBrief | None = None
    members: list[UserBrief] = Field(default_factory=list)
    children: list[DepartmentNode] = Field(default_factory=list)


class RoleInfo(BaseModel):
    id: str
    role_name: str
    role_code: str


class DepartmentInfo(BaseModel):
    id: str
    name: str


class OrgUser(BaseModel):
    id: str
    username: str
    display_name: str
    status: str
    department: DepartmentInfo
    roles: list[RoleInfo] = Field(default_factory=list)


class UserCreateRequest(BaseModel):
    username: str
    password: str
    display_name: str
    department_id: str
    role_ids: list[str] = Field(default_factory=list)
    status: str = "active"


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    department_id: str | None = None
    role_ids: list[str] | None = None
    status: str | None = None
    password: str | None = None


class OrgRole(BaseModel):
    id: str
    role_name: str
    role_code: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class RolePermissionsRequest(BaseModel):
    permissions: list[str]


UserRecord = dict[str, Any]
