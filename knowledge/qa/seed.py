from __future__ import annotations

from typing import Any

from knowledge.units.schemas import utc_now_iso
from knowledge.units.service import KnowledgeService

EXAMPLE_UNIT_ID = "ku-example-demo"


def seed_example_knowledge_unit(knowledge: KnowledgeService) -> dict[str, Any]:
    existing = knowledge.get_unit(EXAMPLE_UNIT_ID)
    if existing is not None:
        return existing
    now = utc_now_iso()
    unit = {
        "id": EXAMPLE_UNIT_ID,
        "unit_code": "KU-EXAMPLE-001",
        "title": "示例产品安全手册",
        "content": "示例知识内容：设备操作前请断电，确认无电压后再检修。",
        "summary": "产品安全操作要点",
        "category": "demo",
        "source_file_name": "example-safety.md",
        "file_type": "md",
        "file_size": 64,
        "status": "published",
        "creator_id": "user-kbadmin",
        "creator_name": "知识管理员",
        "created_at": now,
        "updated_at": now,
        "data_permissions": [
            {"type": "user", "id": "user-alice", "name": "Alice"},
        ],
        "permission_summary": "用户:Alice",
        "tags": ["demo", "safety"],
        "attachments": [],
    }
    return knowledge.insert_unit(unit)
