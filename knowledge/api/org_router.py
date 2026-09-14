from __future__ import annotations

from fastapi import APIRouter, Depends

from knowledge.api.deps import get_current_user, get_org_service
from knowledge.auth.schemas import MeResponse
from knowledge.org.schemas import (
    DepartmentNode,
    DepartmentUpdateRequest,
    OrgRole,
    OrgUser,
    PermissionNode,
    RolePermissionsRequest,
    UserCreateRequest,
    UserUpdateRequest,
)
from knowledge.org.service import OrgService

router = APIRouter(prefix="/org", tags=["org"])


@router.get("/departments", response_model=list[DepartmentNode])
def list_departments(
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> list[DepartmentNode]:
    org_service.require_any_permission(
        list(user.permissions),
        ["menu:org", "dept:manage", "user:view"],
    )
    return org_service.list_department_tree()


@router.put("/departments/{department_id}", response_model=DepartmentNode)
def update_department(
    department_id: str,
    body: DepartmentUpdateRequest,
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> DepartmentNode:
    org_service.require_permission(list(user.permissions), "dept:manage")
    return org_service.update_department(department_id, body)


@router.get("/users", response_model=list[OrgUser])
def list_users(
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> list[OrgUser]:
    org_service.require_permission(list(user.permissions), "user:view")
    return org_service.list_users()


@router.post("/users", response_model=OrgUser)
def create_user(
    body: UserCreateRequest,
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> OrgUser:
    org_service.require_permission(list(user.permissions), "user:create")
    return org_service.create_user(body)


@router.put("/users/{user_id}", response_model=OrgUser)
def update_user(
    user_id: str,
    body: UserUpdateRequest,
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> OrgUser:
    org_service.require_permission(list(user.permissions), "user:update")
    return org_service.update_user(user_id, body)


@router.get("/roles", response_model=list[OrgRole])
def list_roles(
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> list[OrgRole]:
    org_service.require_any_permission(list(user.permissions), ["role:manage", "menu:org"])
    return org_service.list_roles()


@router.post("/roles/{role_id}/permissions", response_model=OrgRole)
def update_role_permissions(
    role_id: str,
    body: RolePermissionsRequest,
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> OrgRole:
    org_service.require_permission(list(user.permissions), "role:manage")
    return org_service.set_role_permissions(role_id, body.permissions)


@router.get("/permissions/tree", response_model=list[PermissionNode])
def permission_tree(
    user: MeResponse = Depends(get_current_user),
    org_service: OrgService = Depends(get_org_service),
) -> list[PermissionNode]:
    org_service.require_any_permission(list(user.permissions), ["role:manage", "menu:org"])
    return org_service.permission_tree()
