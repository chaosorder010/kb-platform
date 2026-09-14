from __future__ import annotations

import jwt
from fastapi import HTTPException, status

from knowledge.auth.jwt import create_access_token, decode_access_token
from knowledge.auth.password import verify_password
from knowledge.auth.repository import AuthRepository
from knowledge.auth.schemas import (
    DepartmentInfo,
    LoginResponse,
    MeResponse,
    RoleInfo,
    UserInfo,
)


class AuthService:
    def __init__(self, repository: AuthRepository) -> None:
        self._repo = repository

    def login(self, username: str, password: str) -> LoginResponse:
        user = self._repo.get_user_by_username(username)
        if user is None or not verify_password(password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户名或密码错误",
            )
        if user.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已停用",
            )
        profile = self._build_user_info(user)
        permissions = self._repo.get_permissions_for_roles(user.get("role_ids", []))
        token = create_access_token(user["id"], {"username": user["username"]})
        return LoginResponse(
            access_token=token,
            user_info=profile,
            permissions=permissions,
        )

    def me(self, token: str) -> MeResponse:
        try:
            payload = decode_access_token(token)
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或过期的登录凭证",
            ) from None
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或过期的登录凭证",
            )
        user = self._repo.get_user_by_id(user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已失效",
            )
        if user.get("status") != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="账号已停用",
            )
        profile = self._build_user_info(user)
        permissions = self._repo.get_permissions_for_roles(user.get("role_ids", []))
        return MeResponse(
            id=profile.id,
            username=profile.username,
            display_name=profile.display_name,
            status=profile.status,
            department=profile.department,
            roles=profile.roles,
            permissions=permissions,
        )

    def _build_user_info(self, user: dict) -> UserInfo:
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
        return UserInfo(
            id=user["id"],
            username=user["username"],
            display_name=user["display_name"],
            status=user["status"],
            department=DepartmentInfo(id=dept["id"], name=dept["name"]),
            roles=roles,
        )
