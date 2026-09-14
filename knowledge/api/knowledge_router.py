from __future__ import annotations

from functools import lru_cache

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from knowledge.api.deps import require_permissions
from knowledge.auth.schemas import MeResponse
from knowledge.units.schemas import (
    AttachmentItem,
    BatchDeleteRequest,
    BatchDeleteResponse,
    CheckPermissionResult,
    CheckPermissionsRequest,
    CheckPermissionsResponse,
    ImportResponse,
    ImportTaskItem,
    ImportTaskStatusResponse,
    KnowledgeUnitItem,
    KnowledgeUnitListResponse,
    KnowledgeUnitUpdateRequest,
    UnitPermissionsRequest,
    UnitVersionItem,
    UnitVersionListResponse,
)
from knowledge.units.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@lru_cache
def get_knowledge_service() -> KnowledgeService:
    from knowledge.units.chunk_writer import MemoryChunkWriter
    from knowledge.units.repository import MongoKnowledgeRepository
    from knowledge.units.service import existing_import_graph_pipeline
    from knowledge.utils.client.storage_clients import StorageClients

    db = StorageClients.get_mongo_db()
    return KnowledgeService(
        repository=MongoKnowledgeRepository(db),
        chunk_writer=MemoryChunkWriter(),
        pipeline=existing_import_graph_pipeline,
    )


@router.post("/import", response_model=ImportResponse)
async def import_knowledge_files(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    category: str = Query(default=""),
    user: MeResponse = Depends(require_permissions("knowledge:create")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ImportResponse:
    payload: list[tuple[str, bytes]] = []
    for upload in files:
        filename = upload.filename or "unnamed.txt"
        content = await upload.read()
        payload.append((filename, content))
    try:
        tasks = service.import_files(
            files=payload,
            creator_id=user.id,
            creator_name=user.display_name,
            category=category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    for task in tasks:
        background_tasks.add_task(service.run_import_task_sync, task["task_id"])

    return ImportResponse(
        message=f"已提交 {len(tasks)} 个导入任务",
        tasks=[ImportTaskItem(**task) for task in tasks],
    )


@router.get("/import/tasks/{task_id}", response_model=ImportTaskStatusResponse)
def get_import_task_status(
    task_id: str,
    user: MeResponse = Depends(require_permissions("knowledge:view")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ImportTaskStatusResponse:
    _ = user
    task = service.get_task_status(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return ImportTaskStatusResponse(
        task_id=task["task_id"],
        unit_id=task["unit_id"],
        status=task.get("status") or "",
        progress=int(task.get("progress") or 0),
        done_list=list(task.get("done_list") or []),
        running_list=list(task.get("running_list") or []),
        filename=task.get("filename") or "",
        error=task.get("error") or "",
    )


@router.get("/units", response_model=KnowledgeUnitListResponse)
def list_knowledge_units(
    q: str | None = Query(default=None),
    title: str | None = Query(default=None),
    category: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: MeResponse = Depends(require_permissions("knowledge:view")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeUnitListResponse:
    _ = user
    result = service.list_units(
        q=q,
        title=title,
        category=category,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return KnowledgeUnitListResponse(
        items=[KnowledgeUnitItem(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/units/{unit_id}", response_model=KnowledgeUnitItem)
def get_knowledge_unit(
    unit_id: str,
    user: MeResponse = Depends(require_permissions("knowledge:view")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeUnitItem:
    _ = user
    unit = service.get_unit(unit_id)
    if unit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="知识单元不存在")
    return KnowledgeUnitItem(**unit)


@router.put("/units/{unit_id}", response_model=KnowledgeUnitItem)
def update_knowledge_unit(
    unit_id: str,
    body: KnowledgeUnitUpdateRequest,
    user: MeResponse = Depends(require_permissions("knowledge:update")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeUnitItem:
    try:
        unit = service.update_unit(
            unit_id,
            editor_id=user.id,
            editor_name=user.display_name,
            title=body.title,
            content=body.content,
            tags=body.tags,
            status=body.status,
            category=body.category,
            summary=body.summary,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KnowledgeUnitItem(**unit)


@router.get("/units/{unit_id}/versions", response_model=UnitVersionListResponse)
def list_unit_versions(
    unit_id: str,
    user: MeResponse = Depends(require_permissions("knowledge:view")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> UnitVersionListResponse:
    _ = user
    try:
        items = service.list_versions(unit_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return UnitVersionListResponse(items=[UnitVersionItem(**item) for item in items])


@router.post("/units/{unit_id}/attachments", response_model=AttachmentItem)
async def upload_unit_attachment(
    unit_id: str,
    file: UploadFile = File(...),
    user: MeResponse = Depends(require_permissions("knowledge:update")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> AttachmentItem:
    content = await file.read()
    try:
        attachment = service.add_attachment(
            unit_id,
            filename=file.filename or "attachment.bin",
            content=content,
            content_type=file.content_type or "",
            uploaded_by=user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return AttachmentItem(**attachment)


@router.post("/units/{unit_id}/permissions", response_model=KnowledgeUnitItem)
def set_unit_permissions(
    unit_id: str,
    body: UnitPermissionsRequest,
    user: MeResponse = Depends(require_permissions("knowledge:permission")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> KnowledgeUnitItem:
    _ = user
    try:
        unit = service.set_permissions(
            unit_id,
            [item.model_dump() for item in body.permissions],
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return KnowledgeUnitItem(**unit)


@router.post("/check-permissions", response_model=CheckPermissionsResponse)
def check_knowledge_permissions(
    body: CheckPermissionsRequest,
    user: MeResponse = Depends(require_permissions("knowledge:view")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> CheckPermissionsResponse:
    _ = user
    results = service.check_permissions(
        unit_ids=body.unit_ids,
        user_id=body.user_id,
        department_id=body.department_id,
        role_ids=body.role_ids,
    )
    return CheckPermissionsResponse(
        results=[CheckPermissionResult(**item) for item in results]
    )


@router.delete("/units", response_model=BatchDeleteResponse)
def delete_knowledge_units(
    body: BatchDeleteRequest,
    user: MeResponse = Depends(require_permissions("knowledge:delete")),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> BatchDeleteResponse:
    _ = user
    deleted = service.delete_units(body.ids)
    return BatchDeleteResponse(deleted=deleted)
