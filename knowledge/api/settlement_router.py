from __future__ import annotations

from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from knowledge.api.deps import require_permissions
from knowledge.auth.schemas import MeResponse
from knowledge.qa.access_logs import (
    MemoryQaAccessLogRepository,
    MongoQaAccessLogRepository,
)
from knowledge.settlement.faqs import MemoryFaqRepository, MongoFaqRepository
from knowledge.settlement.service import SettlementService

router = APIRouter(prefix="/settlement", tags=["settlement"])


class ReviewRequest(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    edited_answer: str = ""


class CacheToggleRequest(BaseModel):
    cache_enabled: bool


@lru_cache
def get_settlement_service() -> SettlementService:
    from knowledge.utils.client.storage_clients import StorageClients

    try:
        db = StorageClients.get_mongo_db()
        faqs = MongoFaqRepository(db)
        logs = MongoQaAccessLogRepository(db)
    except Exception:
        faqs = MemoryFaqRepository()
        logs = MemoryQaAccessLogRepository()
    return SettlementService(faqs=faqs, access_logs=logs)


@router.get("/faqs/recommendations")
def list_recommendations(
    refresh: bool = Query(default=True),
    user: MeResponse = Depends(require_permissions("settlement:manage")),
    service: SettlementService = Depends(get_settlement_service),
):
    _ = user
    items = service.mine_recommendations() if refresh else service.list_recommendations()
    return {"items": items}


@router.get("/faqs")
def list_faqs(
    status_filter: Optional[str] = Query(default="published", alias="status"),
    user: MeResponse = Depends(require_permissions("settlement:manage")),
    service: SettlementService = Depends(get_settlement_service),
):
    _ = user
    if status_filter == "pending_review":
        items = service.list_recommendations()
    elif status_filter == "published" or not status_filter:
        items = service.list_published()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status 仅支持 pending_review 或 published",
        )
    return {"items": items}


@router.post("/faqs/{faq_id}/review")
def review_faq(
    faq_id: str,
    body: ReviewRequest,
    user: MeResponse = Depends(require_permissions("settlement:manage")),
    service: SettlementService = Depends(get_settlement_service),
):
    try:
        item = service.review(
            faq_id,
            action=body.action,
            edited_answer=body.edited_answer,
            reviewer_id=user.id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ 不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return item


@router.post("/faqs/{faq_id}/cache")
def toggle_faq_cache(
    faq_id: str,
    body: CacheToggleRequest,
    user: MeResponse = Depends(require_permissions("settlement:manage")),
    service: SettlementService = Depends(get_settlement_service),
):
    _ = user
    try:
        return service.set_cache_enabled(faq_id, body.cache_enabled)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="FAQ 不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
