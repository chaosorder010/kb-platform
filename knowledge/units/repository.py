from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class KnowledgeRepository(Protocol):
    def insert_unit(self, unit: dict[str, Any]) -> dict[str, Any]: ...

    def update_unit(self, unit_id: str, patch: dict[str, Any]) -> dict[str, Any] | None: ...

    def get_unit(self, unit_id: str) -> dict[str, Any] | None: ...

    def list_units(
        self,
        *,
        q: str | None = None,
        title: str | None = None,
        category: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]: ...

    def save_task(self, task: dict[str, Any]) -> dict[str, Any]: ...

    def update_task(self, task_id: str, patch: dict[str, Any]) -> dict[str, Any] | None: ...

    def get_task(self, task_id: str) -> dict[str, Any] | None: ...

    def save_chunks(self, unit_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]: ...

    def get_chunks(self, unit_id: str) -> list[dict[str, Any]]: ...


class MemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._units: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._chunks: dict[str, list[dict[str, Any]]] = {}

    def insert_unit(self, unit: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(unit)
        self._units[stored["id"]] = stored
        return deepcopy(stored)

    def update_unit(self, unit_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        current = self._units.get(unit_id)
        if current is None:
            return None
        current.update(patch)
        return deepcopy(current)

    def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        unit = self._units.get(unit_id)
        return deepcopy(unit) if unit else None

    def list_units(
        self,
        *,
        q: str | None = None,
        title: str | None = None,
        category: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        items = list(self._units.values())
        if q:
            needle = q.lower()
            items = [
                u
                for u in items
                if needle in (u.get("title") or "").lower()
                or needle in (u.get("unit_code") or "").lower()
                or needle in (u.get("source_file_name") or "").lower()
            ]
        if title:
            needle = title.lower()
            items = [u for u in items if needle in (u.get("title") or "").lower()]
        if category:
            items = [u for u in items if u.get("category") == category]
        if status:
            items = [u for u in items if u.get("status") == status]
        items.sort(key=lambda u: u.get("created_at", ""), reverse=True)
        total = len(items)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        return [deepcopy(u) for u in items[start:end]], total

    def save_task(self, task: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(task)
        self._tasks[stored["task_id"]] = stored
        return deepcopy(stored)

    def update_task(self, task_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        current = self._tasks.get(task_id)
        if current is None:
            return None
        current.update(patch)
        return deepcopy(current)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        task = self._tasks.get(task_id)
        return deepcopy(task) if task else None

    def save_chunks(self, unit_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        stored = [deepcopy(c) for c in chunks]
        self._chunks[unit_id] = stored
        return deepcopy(stored)

    def get_chunks(self, unit_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._chunks.get(unit_id, []))


class MongoKnowledgeRepository:
    def __init__(self, db) -> None:
        self._db = db

    def insert_unit(self, unit: dict[str, Any]) -> dict[str, Any]:
        self._db.knowledge_units.insert_one(deepcopy(unit))
        return deepcopy(unit)

    def update_unit(self, unit_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        self._db.knowledge_units.update_one({"id": unit_id}, {"$set": patch})
        return self.get_unit(unit_id)

    def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        return self._db.knowledge_units.find_one({"id": unit_id}, {"_id": 0})

    def list_units(
        self,
        *,
        q: str | None = None,
        title: str | None = None,
        category: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        and_clauses: list[dict[str, Any]] = []
        if q:
            and_clauses.append(
                {
                    "$or": [
                        {"title": {"$regex": q, "$options": "i"}},
                        {"unit_code": {"$regex": q, "$options": "i"}},
                        {"source_file_name": {"$regex": q, "$options": "i"}},
                    ]
                }
            )
        if title:
            and_clauses.append({"title": {"$regex": title, "$options": "i"}})
        if category:
            and_clauses.append({"category": category})
        if status:
            and_clauses.append({"status": status})
        if and_clauses:
            query["$and"] = and_clauses
        total = self._db.knowledge_units.count_documents(query)
        cursor = (
            self._db.knowledge_units.find(query, {"_id": 0})
            .sort("created_at", -1)
            .skip(max(page - 1, 0) * page_size)
            .limit(page_size)
        )
        return list(cursor), total

    def save_task(self, task: dict[str, Any]) -> dict[str, Any]:
        self._db.import_tasks.insert_one(deepcopy(task))
        return deepcopy(task)

    def update_task(self, task_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        self._db.import_tasks.update_one({"task_id": task_id}, {"$set": patch})
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        return self._db.import_tasks.find_one({"task_id": task_id}, {"_id": 0})

    def save_chunks(self, unit_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._db.unit_chunks.delete_many({"unit_id": unit_id})
        if chunks:
            self._db.unit_chunks.insert_many(deepcopy(chunks))
        return deepcopy(chunks)

    def get_chunks(self, unit_id: str) -> list[dict[str, Any]]:
        return list(self._db.unit_chunks.find({"unit_id": unit_id}, {"_id": 0}))
