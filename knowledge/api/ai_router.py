from __future__ import annotations

import logging
import threading
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from knowledge.api.deps import require_permissions
from knowledge.api.knowledge_router import get_knowledge_service
from knowledge.auth.schemas import MeResponse
from knowledge.qa.access_logs import (
    MemoryQaAccessLogRepository,
    MongoQaAccessLogRepository,
)
from knowledge.qa.seed import seed_example_knowledge_unit
from knowledge.qa.service import ChatService
from knowledge.utils.sse_util import create_sse_queue, sse_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


class ChatStreamRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: Optional[str] = Field(None)


class ChatHistoryItem(BaseModel):
    id: str = Field("", alias="_id")
    session_id: str = ""
    role: str = ""
    text: str = ""
    rewritten_query: str = ""
    item_names: list[str] = Field(default_factory=list)
    ts: Optional[float] = None

    model_config = {"populate_by_name": True}


class ChatHistoryResponse(BaseModel):
    session_id: str
    items: list[ChatHistoryItem]


@lru_cache
def get_chat_service() -> ChatService:
    from knowledge.utils.client.storage_clients import StorageClients

    knowledge = get_knowledge_service()
    seed_example_knowledge_unit(knowledge)
    try:
        access_logs = MongoQaAccessLogRepository(StorageClients.get_mongo_db())
    except Exception:
        logger.exception("Mongo qa access logs unavailable; falling back to memory")
        access_logs = MemoryQaAccessLogRepository()
    return ChatService(
        knowledge_service=knowledge,
        access_logs=access_logs,
    )


@router.post("/chat/stream")
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    user: MeResponse = Depends(require_permissions("ai:access")),
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    session_id = body.session_id or service.generate_session_id()
    task_id = service.generate_task_id()
    create_sse_queue(task_id=task_id)

    def _run() -> None:
        service.run_chat(
            question=body.question,
            session_id=session_id,
            task_id=task_id,
            user=user,
            is_stream=True,
        )

    worker = threading.Thread(target=_run, name=f"chat-{task_id}", daemon=True)
    worker.start()

    headers = {
        "X-Session-Id": session_id,
        "X-Task-Id": task_id,
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        content=sse_generator(task_id, request),
        media_type="text/event-stream",
        headers=headers,
    )


@router.get("/chat/history/{session_id}", response_model=ChatHistoryResponse)
def chat_history(
    session_id: str,
    limit: int = 50,
    user: MeResponse = Depends(require_permissions("ai:access")),
    service: ChatService = Depends(get_chat_service),
) -> ChatHistoryResponse:
    items = service.get_history(session_id, user_id=user.id, limit=limit)
    return ChatHistoryResponse(
        session_id=session_id,
        items=[ChatHistoryItem.model_validate(item) for item in items],
    )


@router.delete("/chat/history/{session_id}")
def clear_chat_history(
    session_id: str,
    user: MeResponse = Depends(require_permissions("ai:access")),
    service: ChatService = Depends(get_chat_service),
):
    count = service.clear_history(session_id, user_id=user.id)
    return {"message": "已清空会话", "deleted_count": count}
