from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from knowledge.units.schemas import utc_now_iso


@runtime_checkable
class QaAccessLogRepository(Protocol):
    def insert(self, entry: dict[str, Any]) -> dict[str, Any]: ...

    def list_all(self) -> list[dict[str, Any]]: ...


class MemoryQaAccessLogRepository:
    def __init__(self) -> None:
        self._entries: list[dict[str, Any]] = []

    def insert(self, entry: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(entry)
        if "id" not in stored:
            stored["id"] = f"log-{uuid4().hex[:12]}"
        if "created_at" not in stored:
            stored["created_at"] = utc_now_iso()
        self._entries.append(stored)
        return deepcopy(stored)

    def list_all(self) -> list[dict[str, Any]]:
        return deepcopy(self._entries)


class MongoQaAccessLogRepository:
    def __init__(self, db) -> None:
        self._db = db

    def insert(self, entry: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(entry)
        if "id" not in stored:
            stored["id"] = f"log-{uuid4().hex[:12]}"
        if "created_at" not in stored:
            stored["created_at"] = utc_now_iso()
        self._db.qa_access_logs.insert_one(deepcopy(stored))
        return stored

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._db.qa_access_logs.find({}, {"_id": 0}))


def build_access_log_entry(
    *,
    session_id: str,
    user_id: str,
    question: str,
    answer: str,
    recalled_unit_ids: list[str],
    authorized_unit_ids: list[str],
    unauthorized_unit_ids: list[str],
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    response_time_ms: int = 0,
) -> dict[str, Any]:
    return {
        "id": f"log-{uuid4().hex[:12]}",
        "session_id": session_id,
        "user_id": user_id,
        "question": question,
        "answer": answer,
        "recalled_unit_ids": list(recalled_unit_ids),
        "authorized_unit_ids": list(authorized_unit_ids),
        "unauthorized_unit_ids": list(unauthorized_unit_ids),
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(total_tokens),
        "response_time_ms": int(response_time_ms),
        "created_at": utc_now_iso(),
    }
