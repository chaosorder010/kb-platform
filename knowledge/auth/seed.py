from __future__ import annotations

from knowledge.auth.password import hash_password

PERMISSION_CODES = {
    "system_admin": [
        "menu:org",
        "menu:knowledge",
        "menu:ai",
        "menu:dashboard",
        "menu:settlement",
        "user:create",
        "user:update",
        "user:delete",
        "user:view",
        "role:manage",
        "dept:manage",
        "knowledge:create",
        "knowledge:update",
        "knowledge:delete",
        "knowledge:view",
        "knowledge:permission",
        "ai:access",
        "dashboard:view",
        "settlement:manage",
    ],
    "kb_admin": [
        "menu:knowledge",
        "menu:ai",
        "menu:dashboard",
        "menu:settlement",
        "knowledge:create",
        "knowledge:update",
        "knowledge:delete",
        "knowledge:view",
        "knowledge:permission",
        "ai:access",
        "dashboard:view",
        "settlement:manage",
    ],
    "user": [
        "menu:ai",
        "knowledge:view",
        "ai:access",
    ],
}

SEED_DEPARTMENTS = [
    {
        "id": "dept-hq",
        "parent_id": None,
        "name": "总部",
        "leader_id": "user-admin",
        "sort_order": 1,
    },
    {
        "id": "dept-ops",
        "parent_id": "dept-hq",
        "name": "运营部",
        "leader_id": "user-kbadmin",
        "sort_order": 2,
    },
]

SEED_ROLES = [
    {
        "id": "role-system-admin",
        "role_name": "系统管理员",
        "role_code": "system_admin",
        "description": "系统与组织管理",
        "permissions": list(PERMISSION_CODES["system_admin"]),
    },
    {
        "id": "role-kb-admin",
        "role_name": "知识管理员",
        "role_code": "kb_admin",
        "description": "知识单元与沉淀管理",
        "permissions": list(PERMISSION_CODES["kb_admin"]),
    },
    {
        "id": "role-user",
        "role_name": "普通用户",
        "role_code": "user",
        "description": "AI 问答访问",
        "permissions": list(PERMISSION_CODES["user"]),
    },
]


def build_seed_users() -> list[dict]:
    return [
        {
            "id": "user-admin",
            "username": "admin",
            "password_hash": hash_password("Admin@123"),
            "display_name": "系统管理员",
            "department_id": "dept-hq",
            "status": "active",
            "role_ids": ["role-system-admin"],
        },
        {
            "id": "user-kbadmin",
            "username": "kbadmin",
            "password_hash": hash_password("Kb@123456"),
            "display_name": "知识管理员",
            "department_id": "dept-ops",
            "status": "active",
            "role_ids": ["role-kb-admin"],
        },
        {
            "id": "user-alice",
            "username": "alice",
            "password_hash": hash_password("User@123"),
            "display_name": "Alice",
            "department_id": "dept-ops",
            "status": "active",
            "role_ids": ["role-user"],
        },
        {
            "id": "user-bob",
            "username": "bob",
            "password_hash": hash_password("User@123"),
            "display_name": "Bob",
            "department_id": "dept-ops",
            "status": "active",
            "role_ids": ["role-user"],
        },
    ]
