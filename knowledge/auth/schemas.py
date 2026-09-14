from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class DepartmentInfo(BaseModel):
    id: str
    name: str


class RoleInfo(BaseModel):
    id: str
    role_name: str
    role_code: str


class UserInfo(BaseModel):
    id: str
    username: str
    display_name: str
    status: str
    department: DepartmentInfo
    roles: list[RoleInfo] = Field(default_factory=list)


class LoginResponse(BaseModel):
    access_token: str
    user_info: UserInfo
    permissions: list[str]


class MeResponse(BaseModel):
    id: str
    username: str
    display_name: str
    status: str
    department: DepartmentInfo
    roles: list[RoleInfo] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


UserRecord = dict[str, Any]
DeptRecord = dict[str, Any]
RoleRecord = dict[str, Any]
