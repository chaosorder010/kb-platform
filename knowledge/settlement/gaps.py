from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from knowledge.units.schemas import utc_now_iso


def gap_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    return (-int(item.get("ask_count") or 0), item.get("last_asked_at") or "")


@runtime_checkable
class GapRepository(Protocol):
    def upsert(self, gap: dict[str, Any]) -> dict[str, Any]: ...

    def get(self, gap_id: str) -> dict[str, Any] | None: ...

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]: ...

    def update(self, gap_id: str, patch: dict[str, Any]) -> dict[str, Any] | None: ...


class MemoryGapRepository:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, Any]] = {}

    def upsert(self, gap: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(gap)
        gap_id = stored.get("id") or f"gap-{uuid4().hex[:12]}"
        stored["id"] = gap_id
        now = utc_now_iso()
        existing = self._items.get(gap_id)
        if existing is None:
            stored.setdefault("created_at", now)
        else:
            stored.setdefault("created_at", existing.get("created_at", now))
        stored["updated_at"] = now
        self._items[gap_id] = stored
        return deepcopy(stored)

    def get(self, gap_id: str) -> dict[str, Any] | None:
        item = self._items.get(gap_id)
        return deepcopy(item) if item else None

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        items = list(self._items.values())
        if status:
            items = [i for i in items if i.get("status") == status]
        items.sort(key=gap_sort_key)
        return deepcopy(items)

    def update(self, gap_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        item = self._items.get(gap_id)
        if item is None:
            return None
        item.update(deepcopy(patch))
        item["updated_at"] = utc_now_iso()
        return deepcopy(item)


class MongoGapRepository:
    def __init__(self, db) -> None:
        self._col = db.knowledge_gaps

    def upsert(self, gap: dict[str, Any]) -> dict[str, Any]:
        stored = deepcopy(gap)
        gap_id = stored.get("id") or f"gap-{uuid4().hex[:12]}"
        stored["id"] = gap_id
        now = utc_now_iso()
        existing = self._col.find_one({"id": gap_id}, {"_id": 0})
        if existing is None:
            stored.setdefault("created_at", now)
        else:
            stored.setdefault("created_at", existing.get("created_at", now))
        stored["updated_at"] = now
        self._col.replace_one({"id": gap_id}, stored, upsert=True)
        return stored

    def get(self, gap_id: str) -> dict[str, Any] | None:
        return self._col.find_one({"id": gap_id}, {"_id": 0})

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        query = {"status": status} if status else {}
        return list(
            self._col.find(query, {"_id": 0}).sort(
                [("ask_count", -1), ("last_asked_at", -1)]
            )
        )

    def update(self, gap_id: str, patch: dict[str, Any]) -> dict[str, Any] | None:
        existing = self.get(gap_id)
        if existing is None:
            return None
        existing.update(deepcopy(patch))
        existing["updated_at"] = utc_now_iso()
        self._col.replace_one({"id": gap_id}, existing)
        return existing
