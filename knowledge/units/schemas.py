from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

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


class KnowledgeUnitListResponse(BaseModel):
    items: list[KnowledgeUnitItem]
    total: int
    page: int = 1
    page_size: int = 20
