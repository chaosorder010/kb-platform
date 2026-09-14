from __future__ import annotations

from knowledge.auth.seed import PERMISSION_CODES

PERMISSION_TREE = [
    {
        "code": "menu:org",
        "name": "组织管理",
        "children": [
            {"code": "user:view", "name": "查看用户"},
            {"code": "user:create", "name": "新增用户"},
            {"code": "user:update", "name": "编辑用户"},
            {"code": "user:delete", "name": "删除用户"},
            {"code": "role:manage", "name": "角色权限"},
            {"code": "dept:manage", "name": "部门管理"},
        ],
    },
    {
        "code": "menu:knowledge",
        "name": "知识库",
        "children": [
            {"code": "knowledge:view", "name": "查看知识"},
            {"code": "knowledge:create", "name": "新建知识"},
            {"code": "knowledge:update", "name": "编辑知识"},
            {"code": "knowledge:delete", "name": "删除知识"},
            {"code": "knowledge:permission", "name": "知识权限"},
        ],
    },
    {
        "code": "menu:ai",
        "name": "AI 对话",
        "children": [
            {"code": "ai:access", "name": "访问对话"},
        ],
    },
    {
        "code": "menu:dashboard",
        "name": "业务看板",
        "children": [
            {"code": "dashboard:view", "name": "查看看板"},
        ],
    },
    {
        "code": "menu:settlement",
        "name": "知识沉淀",
        "children": [
            {"code": "settlement:manage", "name": "沉淀管理"},
        ],
    },
]

ALL_PERMISSION_CODES = sorted(
    {
        code
        for codes in PERMISSION_CODES.values()
        for code in codes
    }
)
