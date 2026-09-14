from __future__ import annotations

from copy import deepcopy
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class KnowledgeRepository(Protocol):
    def insert_unit(self, unit: dict[str, Any]) -> dict[str, Any]: ...

    def update_unit(self, unit_id: str, patch: dict[str, Any]) -> dict[str, Any] | None: ...

    def get_unit(self, unit_id: str) -> dict[str, Any] | None: ...

    def delete_units(self, unit_ids: list[str]) -> int: ...

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

    def save_version(self, version: dict[str, Any]) -> dict[str, Any]: ...

    def list_versions(self, unit_id: str) -> list[dict[str, Any]]: ...

    def save_attachment(self, attachment: dict[str, Any]) -> dict[str, Any]: ...

    def list_attachments(self, unit_id: str) -> list[dict[str, Any]]: ...

    def put_object(self, object_key: str, content: bytes) -> None: ...

    def get_object(self, object_key: str) -> bytes | None: ...


class MemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._units: dict[str, dict[str, Any]] = {}
        self._tasks: dict[str, dict[str, Any]] = {}
        self._chunks: dict[str, list[dict[str, Any]]] = {}
        self._versions: dict[str, list[dict[str, Any]]] = {}
        self._attachments: dict[str, list[dict[str, Any]]] = {}
        self._objects: dict[str, bytes] = {}

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

    def delete_units(self, unit_ids: list[str]) -> int:
        deleted = 0
        for unit_id in unit_ids:
            if unit_id in self._units:
                del self._units[unit_id]
                self._versions.pop(unit_id, None)
                self._attachments.pop(unit_id, None)
                self._chunks.pop(unit_id, None)
                deleted += 1
        return deleted

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
        items.sort(key=lambda u: u.get("created_at") or "", reverse=True)
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

    def save_version(self, version: dict[str, Any]) -> dict[str, Any]:
        unit_id = version["unit_id"]
        bucket = self._versions.setdefault(unit_id, [])
        stored = deepcopy(version)
        bucket.append(stored)
        return deepcopy(stored)

    def list_versions(self, unit_id: str) -> list[dict[str, Any]]:
        items = self._versions.get(unit_id, [])
        ordered = sorted(items, key=lambda v: v.get("version", 0), reverse=True)
        return deepcopy(ordered)

    def save_attachment(self, attachment: dict[str, Any]) -> dict[str, Any]:
        unit_id = attachment["unit_id"]
        bucket = self._attachments.setdefault(unit_id, [])
        stored = deepcopy(attachment)
        bucket.append(stored)
        return deepcopy(stored)

    def list_attachments(self, unit_id: str) -> list[dict[str, Any]]:
        return deepcopy(self._attachments.get(unit_id, []))

    def put_object(self, object_key: str, content: bytes) -> None:
        self._objects[object_key] = content

    def get_object(self, object_key: str) -> bytes | None:
        data = self._objects.get(object_key)
        return bytes(data) if data is not None else None


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

    def delete_units(self, unit_ids: list[str]) -> int:
        result = self._db.knowledge_units.delete_many({"id": {"$in": unit_ids}})
        self._db.knowledge_unit_versions.delete_many({"unit_id": {"$in": unit_ids}})
        self._db.unit_attachments.delete_many({"unit_id": {"$in": unit_ids}})
        self._db.unit_chunks.delete_many({"unit_id": {"$in": unit_ids}})
        return int(result.deleted_count)

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

    def save_version(self, version: dict[str, Any]) -> dict[str, Any]:
        self._db.knowledge_unit_versions.insert_one(deepcopy(version))
        return deepcopy(version)

    def list_versions(self, unit_id: str) -> list[dict[str, Any]]:
        cursor = self._db.knowledge_unit_versions.find(
            {"unit_id": unit_id}, {"_id": 0}
        ).sort("version", -1)
        return list(cursor)

    def save_attachment(self, attachment: dict[str, Any]) -> dict[str, Any]:
        self._db.unit_attachments.insert_one(deepcopy(attachment))
        return deepcopy(attachment)

    def list_attachments(self, unit_id: str) -> list[dict[str, Any]]:
        return list(
            self._db.unit_attachments.find({"unit_id": unit_id}, {"_id": 0})
        )

    def put_object(self, object_key: str, content: bytes) -> None:
        import io
        import os

        from knowledge.utils.client.storage_clients import StorageClients

        client = StorageClients.get_minio_client()
        bucket = os.environ["MINIO_BUCKET_NAME"]
        client.put_object(
            bucket,
            object_key,
            io.BytesIO(content),
            length=len(content),
            content_type="application/octet-stream",
        )
        self._db.unit_objects.update_one(
            {"object_key": object_key},
            {"$set": {"object_key": object_key, "size": len(content), "storage": "minio"}},
            upsert=True,
        )

    def get_object(self, object_key: str) -> bytes | None:
        import os

        from knowledge.utils.client.storage_clients import StorageClients

        client = StorageClients.get_minio_client()
        bucket = os.environ["MINIO_BUCKET_NAME"]
        response = client.get_object(bucket, object_key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
