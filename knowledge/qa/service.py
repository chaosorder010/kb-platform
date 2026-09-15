from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable

from knowledge.auth.schemas import MeResponse
from knowledge.qa.access_logs import (
    MemoryQaAccessLogRepository,
    QaAccessLogRepository,
    build_access_log_entry,
)
from knowledge.units.service import KnowledgeService
from knowledge.utils.mongo_history_util import clear_history, get_recent_messages
from knowledge.utils.sse_util import SSEEvent, push_sse_event
from knowledge.utils.task_util import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_PROCESSING,
    update_task_status,
)

logger = logging.getLogger(__name__)

GraphRunner = Callable[[dict[str, Any]], dict[str, Any] | None]


class ChatService:
    """Authenticated QA orchestration: graph + authz context + access logs."""

    def __init__(
        self,
        knowledge_service: KnowledgeService,
        access_logs: QaAccessLogRepository | None = None,
        graph_runner: GraphRunner | None = None,
        history_getter: Callable[[str, int], list[dict[str, Any]]] | None = None,
        history_clearer: Callable[[str], int] | None = None,
        faq_matcher: Callable[[str], dict[str, Any] | None] | None = None,
    ) -> None:
        self._knowledge = knowledge_service
        self._access_logs = access_logs or MemoryQaAccessLogRepository()
        self._graph_runner = graph_runner or self._default_graph_runner
        self._history_getter = history_getter or get_recent_messages
        self._history_clearer = history_clearer or clear_history
        self._faq_matcher = faq_matcher

    @staticmethod
    def generate_session_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def generate_task_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def scoped_session_id(session_id: str, user_id: str) -> str:
        """Bind client session id to the authenticated user for history isolation."""
        return f"{user_id}:{session_id}"

    def run_chat(
        self,
        *,
        question: str,
        session_id: str,
        task_id: str,
        user: MeResponse,
        is_stream: bool = True,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        update_task_status(task_id=task_id, status_name=TASK_STATUS_PROCESSING)
        scoped_session = self.scoped_session_id(session_id, user.id)

        def permission_checker(unit_ids: list[str]) -> list[dict[str, Any]]:
            return self._knowledge.check_permissions(
                unit_ids=unit_ids,
                user_id=user.id,
                department_id=user.department.id if user.department else "",
                role_ids=[role.id for role in user.roles],
            )

        state: dict[str, Any] = {
            "session_id": scoped_session,
            "task_id": task_id,
            "original_query": question,
            "is_stream": is_stream,
            "user_id": user.id,
            "department_id": user.department.id if user.department else "",
            "role_ids": [role.id for role in user.roles],
            "permission_checker": permission_checker,
            "answer": "",
            "reranked_docs": [],
            "authorized_unit_ids": [],
            "unauthorized_unit_ids": [],
            "unauthorized_units": [],
            "recalled_unit_ids": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        faq_hit = self._faq_matcher(question) if self._faq_matcher else None
        if faq_hit:
            answer = str(faq_hit.get("answer") or "")
            state["answer"] = answer
            state["faq_id"] = faq_hit.get("id")
            state["faq_cache_hit"] = True
            related = list(faq_hit.get("related_unit_ids") or [])
            if not related and faq_hit.get("related_unit_id"):
                related = [str(faq_hit.get("related_unit_id"))]
            state["authorized_unit_ids"] = [uid for uid in related if uid]
            state["recalled_unit_ids"] = list(state["authorized_unit_ids"])
            if is_stream:
                push_sse_event(
                    task_id=task_id,
                    event=SSEEvent.DELTA,
                    data={"content": answer},
                )
                push_sse_event(
                    task_id=task_id,
                    event=SSEEvent.FINAL,
                    data={
                        "answer": answer,
                        "unauthorized_units": [],
                        "authorized_unit_ids": state["authorized_unit_ids"],
                        "unauthorized_unit_ids": [],
                        "references": [
                            {
                                "unit_id": uid,
                                "title": uid,
                            }
                            for uid in state["authorized_unit_ids"]
                        ],
                        "faq_cache_hit": True,
                        "faq_id": faq_hit.get("id"),
                        "match_score": faq_hit.get("match_score"),
                    },
                )
            update_task_status(task_id=task_id, status_name=TASK_STATUS_COMPLETED)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self._write_access_log(
                session_id=session_id,
                user_id=user.id,
                question=question,
                state=state,
                response_time_ms=elapsed_ms,
            )
            return state

        try:
            result = self._graph_runner(state) or state
            if isinstance(result, dict):
                state.update(result)
            update_task_status(task_id=task_id, status_name=TASK_STATUS_COMPLETED)
        except Exception as exc:
            logger.exception("chat graph failed: %s", exc)
            update_task_status(task_id=task_id, status_name=TASK_STATUS_FAILED)
            state["answer"] = "问答处理失败，请稍后重试。"
            if is_stream:
                push_sse_event(
                    task_id=task_id,
                    event=SSEEvent.FINAL,
                    data={
                        "answer": state["answer"],
                        "error": str(exc),
                        "unauthorized_units": state.get("unauthorized_units") or [],
                        "authorized_unit_ids": state.get("authorized_unit_ids") or [],
                        "unauthorized_unit_ids": state.get("unauthorized_unit_ids") or [],
                        "references": [],
                    },
                )
            # Do not re-raise: SSE clients must observe FINAL and close cleanly.
        finally:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            self._write_access_log(
                session_id=session_id,
                user_id=user.id,
                question=question,
                state=state,
                response_time_ms=elapsed_ms,
            )

        return state

    def get_history(
        self,
        session_id: str,
        *,
        user_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        scoped = self.scoped_session_id(session_id, user_id)
        records = self._history_getter(scoped, limit)
        return [
            {
                "_id": str(r.get("_id", "")),
                "session_id": session_id,
                "role": r.get("role", ""),
                "text": r.get("text", ""),
                "rewritten_query": r.get("rewritten_query") or "",
                "item_names": r.get("item_names", []),
                "ts": r.get("ts"),
            }
            for r in records
        ]

    def clear_history(self, session_id: str, *, user_id: str) -> int:
        scoped = self.scoped_session_id(session_id, user_id)
        return self._history_clearer(scoped)

    def _write_access_log(
        self,
        *,
        session_id: str,
        user_id: str,
        question: str,
        state: dict[str, Any],
        response_time_ms: int,
    ) -> None:
        scores = [
            float(doc["score"])
            for doc in (state.get("reranked_docs") or [])
            if doc.get("score") is not None
        ]
        entry = build_access_log_entry(
            session_id=session_id,
            user_id=user_id,
            question=question,
            answer=str(state.get("answer") or ""),
            recalled_unit_ids=list(state.get("recalled_unit_ids") or []),
            authorized_unit_ids=list(state.get("authorized_unit_ids") or []),
            unauthorized_unit_ids=list(state.get("unauthorized_unit_ids") or []),
            prompt_tokens=int(state.get("prompt_tokens") or 0),
            completion_tokens=int(state.get("completion_tokens") or 0),
            total_tokens=int(state.get("total_tokens") or 0),
            response_time_ms=response_time_ms,
            faq_cache_hit=bool(state.get("faq_cache_hit")),
            max_recall_score=max(scores) if scores else None,
        )
        self._access_logs.insert(entry)

    @staticmethod
    def _default_graph_runner(state: dict[str, Any]) -> dict[str, Any]:
        from knowledge.processor.query_processor.main_graph import query_app

        return query_app.invoke(state)
