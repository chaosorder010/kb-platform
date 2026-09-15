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
from knowledge.api.knowledge_router import get_knowledge_service
from knowledge.settlement.faqs import MemoryFaqRepository, MongoFaqRepository
from knowledge.settlement.gaps import MemoryGapRepository, MongoGapRepository
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

    knowledge = get_knowledge_service()
    try:
        db = StorageClients.get_mongo_db()
        faqs = MongoFaqRepository(db)
        gaps = MongoGapRepository(db)
        logs = MongoQaAccessLogRepository(db)
    except Exception:
        faqs = MemoryFaqRepository()
        gaps = MemoryGapRepository()
        logs = MemoryQaAccessLogRepository()
    return SettlementService(
        faqs=faqs,
        gaps=gaps,
        access_logs=logs,
        knowledge_service=knowledge,
    )


@router.get("/faqs/recommendations")
def list_recommendations(
    refresh: bool = Query(default=False),
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


class GapStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(unresolved|resolved|ignored)$")


class GapCreateUnitRequest(BaseModel):
    title: str = ""
    content: str = ""


@router.get("/knowledge-gaps")
def list_knowledge_gaps(
    refresh: bool = Query(default=False),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    user: MeResponse = Depends(require_permissions("settlement:manage")),
    service: SettlementService = Depends(get_settlement_service),
):
    _ = user
    if refresh:
        items = service.mine_knowledge_gaps()
    else:
        items = service.list_knowledge_gaps()
    if status_filter:
        items = [i for i in items if i.get("status") == status_filter]
    return {"items": items}


@router.post("/knowledge-gaps/{gap_id}/status")
def update_knowledge_gap_status(
    gap_id: str,
    body: GapStatusRequest,
    user: MeResponse = Depends(require_permissions("settlement:manage")),
    service: SettlementService = Depends(get_settlement_service),
):
    _ = user
    try:
        return service.update_gap_status(gap_id, body.status)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="缺口不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/knowledge-gaps/{gap_id}/create-unit")
def create_unit_from_gap(
    gap_id: str,
    body: GapCreateUnitRequest,
    user: MeResponse = Depends(require_permissions("settlement:manage")),
    service: SettlementService = Depends(get_settlement_service),
):
    try:
        return service.create_unit_from_gap(
            gap_id,
            creator_id=user.id,
            creator_name=user.display_name,
            title=body.title,
            content=body.content,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="缺口不存在") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
