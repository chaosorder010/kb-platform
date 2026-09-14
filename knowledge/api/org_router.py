from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status

from knowledge.api.deps import get_auth_service, get_org_service
from knowledge.auth.service import AuthService
from knowledge.org.schemas import (
    DepartmentNode,
    OrgRole,
    OrgUser,
    PermissionNode,
    RolePermissionsRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from knowledge.org.service import OrgService

router = APIRouter(prefix="/org", tags=["org"])


def _extract_bearer(authorization: str | None) -> str:
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


def _current_permissions(
    authorization: str | None,
    auth_service: AuthService,
) -> list[str]:
    me = auth_service.me(_extract_bearer(authorization))
    return list(me.permissions)


@router.get("/departments", response_model=list[DepartmentNode])
def list_departments(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    org_service: OrgService = Depends(get_org_service),
) -> list[DepartmentNode]:
    permissions = _current_permissions(authorization, auth_service)
    org_service.require_any_permission(
        permissions,
        ["menu:org", "dept:manage", "user:view"],
    )
    return org_service.list_department_tree()


@router.get("/users", response_model=list[OrgUser])
def list_users(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    org_service: OrgService = Depends(get_org_service),
) -> list[OrgUser]:
    permissions = _current_permissions(authorization, auth_service)
    org_service.require_permission(permissions, "user:view")
    return org_service.list_users()


@router.post("/users", response_model=OrgUser)
def create_user(
    body: UserCreateRequest,
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    org_service: OrgService = Depends(get_org_service),
) -> OrgUser:
    permissions = _current_permissions(authorization, auth_service)
    org_service.require_permission(permissions, "user:create")
    return org_service.create_user(body)


@router.put("/users/{user_id}", response_model=OrgUser)
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    org_service: OrgService = Depends(get_org_service),
) -> OrgUser:
    permissions = _current_permissions(authorization, auth_service)
    org_service.require_permission(permissions, "user:update")
    return org_service.update_user(user_id, body)


@router.get("/roles", response_model=list[OrgRole])
def list_roles(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    org_service: OrgService = Depends(get_org_service),
) -> list[OrgRole]:
    permissions = _current_permissions(authorization, auth_service)
    org_service.require_any_permission(permissions, ["role:manage", "menu:org"])
    return org_service.list_roles()


@router.post("/roles/{role_id}/permissions", response_model=OrgRole)
def update_role_permissions(
    role_id: str,
    body: RolePermissionsRequest,
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    org_service: OrgService = Depends(get_org_service),
) -> OrgRole:
    permissions = _current_permissions(authorization, auth_service)
    org_service.require_permission(permissions, "role:manage")
    return org_service.set_role_permissions(role_id, body.permissions)


@router.get("/permissions/tree", response_model=list[PermissionNode])
def permission_tree(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
    org_service: OrgService = Depends(get_org_service),
) -> list[PermissionNode]:
    permissions = _current_permissions(authorization, auth_service)
    org_service.require_any_permission(permissions, ["role:manage", "menu:org"])
    return org_service.permission_tree()
