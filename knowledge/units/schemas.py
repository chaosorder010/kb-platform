from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ImportTaskItem(BaseModel):
    task_id: str
    unit_id: str
    filename: str


class ImportResponse(BaseModel):
    message: str
    tasks: list[ImportTaskItem]


class ImportTaskStatusResponse(BaseModel):
    task_id: str
    unit_id: str
    status: str
    progress: int = 0
    done_list: list[str] = Field(default_factory=list)
    running_list: list[str] = Field(default_factory=list)
    filename: str = ""
    error: str = ""


class AttachmentItem(BaseModel):
    id: str
    filename: str
    object_key: str
    size: int
    content_type: str = ""
    uploaded_by: str = ""
    uploaded_at: str = ""


class KnowledgeUnitItem(BaseModel):
    id: str
    unit_code: str
    title: str
    category: str = ""
    file_type: str
    source_file_name: str
    permission_summary: str
    data_permissions: list[dict[str, Any]] = Field(default_factory=list)
    creator_id: str
    creator_name: str
    created_at: str
    updated_at: str
    status: str
    summary: str = ""
    content: str = ""
    file_size: int = 0
    tags: list[str] = Field(default_factory=list)
    attachments: list[AttachmentItem] = Field(default_factory=list)


class KnowledgeUnitListResponse(BaseModel):
    items: list[KnowledgeUnitItem]
    total: int
    page: int = 1
    page_size: int = 20


class KnowledgeUnitUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    category: str | None = None
    summary: str | None = None


class UnitVersionItem(BaseModel):
    id: str
    unit_id: str
    version: int
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    status: str
    editor_id: str
    editor_name: str = ""
    created_at: str


class UnitVersionListResponse(BaseModel):
    items: list[UnitVersionItem]


PermissionType = Literal["global", "department", "role", "user"]


class DataPermissionItem(BaseModel):
    type: PermissionType
    id: str
    name: str = ""


class UnitPermissionsRequest(BaseModel):
    permissions: list[DataPermissionItem]


class CheckPermissionsRequest(BaseModel):
    unit_ids: list[str]
    user_id: str
    department_id: str = ""
    role_ids: list[str] = Field(default_factory=list)


class CheckPermissionResult(BaseModel):
    unit_id: str
    authorized: bool


class CheckPermissionsResponse(BaseModel):
    results: list[CheckPermissionResult]


class BatchDeleteRequest(BaseModel):
    ids: list[str]


class BatchDeleteResponse(BaseModel):
    deleted: int
