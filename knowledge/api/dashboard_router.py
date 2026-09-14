from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, Depends, Query

from knowledge.api.deps import require_permissions
from knowledge.api.knowledge_router import get_knowledge_service
from knowledge.auth.schemas import MeResponse
from knowledge.dashboard.service import DashboardService
from knowledge.qa.access_logs import (
    MemoryQaAccessLogRepository,
    MongoQaAccessLogRepository,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@lru_cache
def get_dashboard_service() -> DashboardService:
    from knowledge.utils.client.storage_clients import StorageClients

    knowledge = get_knowledge_service()
    try:
        access_logs = MongoQaAccessLogRepository(StorageClients.get_mongo_db())
    except Exception:
        access_logs = MemoryQaAccessLogRepository()

    def unit_counter() -> int:
        return int(knowledge.list_units(page=1, page_size=1).get("total") or 0)

    def unit_title_lookup(unit_id: str) -> str:
        unit = knowledge.get_unit(unit_id)
        if unit and unit.get("title"):
            return str(unit["title"])
        return unit_id

    return DashboardService(
        access_logs=access_logs,
        unit_counter=unit_counter,
        unit_title_lookup=unit_title_lookup,
    )


@router.get("/metrics")
def dashboard_metrics(
    user: MeResponse = Depends(require_permissions("dashboard:view")),
    service: DashboardService = Depends(get_dashboard_service),
):
    _ = user
    return service.metrics()


@router.get("/rankings/questions")
def ranking_questions(
    limit: int = Query(default=10, ge=1, le=100),
    user: MeResponse = Depends(require_permissions("dashboard:view")),
    service: DashboardService = Depends(get_dashboard_service),
):
    _ = user
    return {"items": service.top_questions(limit=limit)}


@router.get("/rankings/units")
def ranking_units(
    limit: int = Query(default=10, ge=1, le=100),
    user: MeResponse = Depends(require_permissions("dashboard:view")),
    service: DashboardService = Depends(get_dashboard_service),
):
    _ = user
    return {"items": service.top_units(limit=limit)}


@router.get("/stats/tokens")
def token_stats(
    granularity: str = Query(default="day"),
    user: MeResponse = Depends(require_permissions("dashboard:view")),
    service: DashboardService = Depends(get_dashboard_service),
):
    _ = user
    return service.token_stats(granularity=granularity)
