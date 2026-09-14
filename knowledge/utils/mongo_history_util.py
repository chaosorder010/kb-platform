import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
from pymongo.collection import Collection
from pymongo import DESCENDING

from knowledge.utils.client.storage_clients import StorageClients

logger = logging.getLogger(__name__)


def _get_collection() -> Collection:
    return StorageClients.get_mongo_db()["chat_message"]


def save_chat_message(
        session_id: str,
        role: str,
        text: str,
        rewritten_query: str = "",
        item_names: List[str] = None,
        message_id: str = None,
        image_url: str = "",
        user_id: str = "",
) -> str:
    ts = datetime.now().timestamp()
    document = {
        "session_id": session_id,
        "user_id": user_id or "",
        "role": role,
        "text": text,
        "rewritten_query": rewritten_query,
        "item_names": item_names or [],
        "image_url": image_url,
        "ts": ts,
    }
    collection = _get_collection()
    if message_id:
        collection.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": document},
        )
        return message_id
    result = collection.insert_one(document)
    return str(result.inserted_id)


def get_recent_messages(
    session_id: str,
    limit: int = 10,
    user_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    try:
        query: Dict[str, Any] = {"session_id": session_id}
        if user_id:
            query["user_id"] = user_id
        cursor = (
            _get_collection()
            .find(query)
            .sort("ts", DESCENDING)
            .limit(limit)
        )
        return list(cursor)
    except Exception as e:
        logger.error(f"Error getting recent messages: {e}")
        return []


def clear_history(session_id: str, user_id: Optional[str] = None) -> int:
    try:
        query: Dict[str, Any] = {"session_id": session_id}
        if user_id:
            query["user_id"] = user_id
        result = _get_collection().delete_many(query)
        logger.info(f"Deleted {result.deleted_count} messages for session {session_id}")
        return result.deleted_count
    except Exception as e:
        logger.error(f"Error clearing history for session {session_id}: {e}")
        return 0
