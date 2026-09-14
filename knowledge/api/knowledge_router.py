from __future__ import annotations

from functools import lru_cache

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
    status,
)

from knowledge.api.deps import get_auth_service
from knowledge.auth.schemas import MeResponse
from knowledge.auth.service import AuthService
from knowledge.units.repository import MemoryKnowledgeRepository
from knowledge.units.schemas import (
    ImportResponse,
    ImportTaskItem,
    ImportTaskStatusResponse,
    KnowledgeUnitItem,
    KnowledgeUnitListResponse,
)
from knowledge.units.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@lru_cache
def get_knowledge_service() -> KnowledgeService:
    return KnowledgeService(repository=MemoryKnowledgeRepository())


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


def get_current_user(
    authorization: str | None = Header(default=None),
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    token = _extract_bearer(authorization)
    return auth_service.me(token)


def require_permissions(*codes: str):
    def _checker(user: MeResponse = Depends(get_current_user)) -> MeResponse:
        missing = [code for code in codes if code not in user.permissions]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="无操作权限",
            )
        return user

    return _checker


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
