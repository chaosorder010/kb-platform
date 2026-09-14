from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ChunkWriter(Protocol):
    def write_chunks(self, unit_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class MemoryChunkWriter:
    def __init__(self) -> None:
        self.written: list[dict[str, Any]] = []

    def write_chunks(self, unit_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = []
        for chunk in chunks:
            row = dict(chunk)
            row["unit_id"] = unit_id
            payload.append(row)
        self.written.extend(payload)
        return payload


class MilvusChunkWriter:
    def write_chunks(self, unit_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        payload = []
        for chunk in chunks:
            row = dict(chunk)
            row["unit_id"] = unit_id
            payload.append(row)
        try:
            from knowledge.utils.client.storage_clients import StorageClients

            client = StorageClients.get_milvus_client()
            collection = "knowledge_chunks"
            if not client.has_collection(collection):
                return payload
            client.insert(collection_name=collection, data=payload)
        except Exception:
            pass
        return payload
