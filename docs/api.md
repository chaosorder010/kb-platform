# 平台 REST API 参考

手写增量：权限码、业务语义与可运行示例。字段级 schema 以 FastAPI OpenAPI（`/docs`）为准。

**权威实现：** `knowledge/api/*_router.py`、`knowledge/api/app_main.py`、`knowledge/auth/seed.py`。

## 约定

| 项 | 说明 |
|----|------|
| 统一前缀 | 全部业务路由挂在 `/api`（含 Health） |
| 认证 | `Authorization: Bearer <access_token>`；`POST /api/auth/login` 返回 `access_token` |
| 免 JWT | `GET /api/health`、整个 `/api/metrics/*` |
| 权限 | 登录后权限码来自角色；缺权返回 `403`，`detail: "无操作权限"`；未登录 `401` |
| 挂载 | `app_main.load_domain_routers()` 仅挂载 auth / org / knowledge / ai / dashboard / settlement / metrics |

### 遗留未挂载

下列模块仍在仓库中，**未**经 `app_main` 挂载，请勿当作当前平台 API：

- `knowledge/api/import_router.py`（旧上传 `/upload`、`/status/{task_id}`）
- `knowledge/api/query_router.py`（旧问答 `/query` 等）

知识导入与问答请使用 Knowledge / AI 模块。

### 权限码（种子）

来源：`knowledge/auth/seed.py` 的 `PERMISSION_CODES`。

| 码 | 语义 |
|----|------|
| `menu:org` / `menu:knowledge` / `menu:ai` / `menu:dashboard` / `menu:settlement` | 前端菜单可见性（部分 Org 列表接口可与管理码二选一） |
| `user:view` / `user:create` / `user:update` / `user:delete` | 用户 CRUD（`user:delete` 已种子，当前无对应 REST） |
| `role:manage` | 角色与权限树管理 |
| `dept:manage` | 部门树维护 |
| `knowledge:view` / `create` / `update` / `delete` / `permission` | 知识单元读、导入、改、批删、数据权限 |
| `ai:access` | AI 问答与会话历史 |
| `dashboard:view` | 运营看板 |
| `settlement:manage` | FAQ 沉淀与知识缺口 |

角色预设：`system_admin`（全量）、`kb_admin`（知识/AI/看板/沉淀）、`user`（`menu:ai` + `knowledge:view` + `ai:access`）。

---

## Auth

前缀：`/api/auth`。登录免 JWT；`/me` 需 JWT。

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `POST` | `/api/auth/login` | — | body：`username`, `password` | `{ access_token, user_info, permissions }` |
| `GET` | `/api/auth/me` | JWT | — | 当前用户 + `permissions[]` |

业务语义：`permissions` 是后续接口鉴权的唯一来源；前端菜单码与操作码一并返回。

---

## Org

前缀：`/api/org`。均需 JWT；权限由 OrgService 校验（`require_permission` / `require_any_permission`）。

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `GET` | `/api/org/departments` | 任一：`menu:org` \| `dept:manage` \| `user:view` | — | 部门树 `DepartmentNode[]`（含 leader / members / children） |
| `PUT` | `/api/org/departments/{department_id}` | `dept:manage` | body：`leader_id?`, `member_ids?` | 更新后的节点 |
| `GET` | `/api/org/users` | `user:view` | — | `OrgUser[]` |
| `POST` | `/api/org/users` | `user:create` | body：`username`, `password`, `display_name`, `department_id`, `role_ids?`, `status?` | 新建用户 |
| `PUT` | `/api/org/users/{user_id}` | `user:update` | body：可选 `display_name` / `department_id` / `role_ids` / `status` / `password` | 更新后用户 |
| `GET` | `/api/org/roles` | 任一：`role:manage` \| `menu:org` | — | `OrgRole[]`（含 `permissions`） |
| `POST` | `/api/org/roles/{role_id}/permissions` | `role:manage` | body：`permissions: string[]` | 覆盖后的角色 |
| `GET` | `/api/org/permissions/tree` | 任一：`role:manage` \| `menu:org` | — | 权限树 `PermissionNode[]` |

业务语义：部门树接口放宽到「能看组织菜单或用户」即可浏览；改部门领导/成员必须 `dept:manage`。角色权限是整表覆盖，不是增量 patch。

---

## Knowledge

前缀：`/api/knowledge`。均需 JWT + 下列权限码。

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `POST` | `/api/knowledge/import` | `knowledge:create` | multipart `files`；query `category?` | `{ message, tasks: [{ task_id, unit_id, filename }] }`；后台跑导入 |
| `GET` | `/api/knowledge/import/tasks/{task_id}` | `knowledge:view` | — | 进度：`status`, `progress`, `done_list`, `running_list`, `error` |
| `GET` | `/api/knowledge/units` | `knowledge:view` | query：`q?`, `title?`, `category?`, `status?`, `page=1`, `page_size=20`（≤100） | `{ items, total, page, page_size }` |
| `GET` | `/api/knowledge/units/{unit_id}` | `knowledge:view` | — | 单条 `KnowledgeUnitItem` |
| `PUT` | `/api/knowledge/units/{unit_id}` | `knowledge:update` | body：可选 title/content/tags/status/category/summary | 更新后单元（写版本） |
| `GET` | `/api/knowledge/units/{unit_id}/versions` | `knowledge:view` | — | `{ items: UnitVersionItem[] }` |
| `POST` | `/api/knowledge/units/{unit_id}/attachments` | `knowledge:update` | multipart `file` | `AttachmentItem` |
| `POST` | `/api/knowledge/units/{unit_id}/permissions` | `knowledge:permission` | body：`permissions[{ type, id, name? }]`，`type` ∈ global/department/role/user | 更新后单元 |
| `POST` | `/api/knowledge/check-permissions` | `knowledge:view` | body：`unit_ids`, `user_id`, `department_id?`, `role_ids?` | `{ results: [{ unit_id, authorized }] }` |
| `DELETE` | `/api/knowledge/units` | `knowledge:delete` | body：`ids: string[]` | `{ deleted: number }` |

业务语义：

- 导入立即返回任务列表，真正图管道在 `BackgroundTasks` 中执行。
- `data_permissions` / `permission_summary` 描述**数据级**可见范围，与 RBAC 权限码正交；`check-permissions` 用于按用户/部门/角色批量探测。
- 删除为批量 body，非路径参数。

---

## AI

前缀：`/api/ai`。均需 `ai:access`。

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `POST` | `/api/ai/chat/stream` | `ai:access` | body：`question`（必填）, `session_id?` | SSE `text/event-stream`；响应头 `X-Session-Id`, `X-Task-Id` |
| `GET` | `/api/ai/chat/history/{session_id}` | `ai:access` | query：`limit=50` | `{ session_id, items[] }`（仅当前用户会话） |
| `DELETE` | `/api/ai/chat/history/{session_id}` | `ai:access` | — | `{ message, deleted_count }` |

业务语义：未传 `session_id` 时服务端生成并在响应头回传。流式问答会写访问日志，供 Dashboard / Settlement 消费。命中已发布且启用缓存的 FAQ 时可能走沉淀快路径（与 Settlement 联动）。

---

## Dashboard

前缀：`/api/dashboard`。均需 `dashboard:view`。数据来自 QA 访问日志 + 知识单元计数。

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `GET` | `/api/dashboard/metrics` | `dashboard:view` | — | `visit_count`, `uv`, `knowledge_unit_count`, `total_tokens`, `avg_response_time_ms` |
| `GET` | `/api/dashboard/rankings/questions` | `dashboard:view` | `limit=10`（1–100） | `{ items: [{ question, count }] }` |
| `GET` | `/api/dashboard/rankings/units` | `dashboard:view` | `limit=10`（1–100） | `{ items: [{ unit_id, title, count }] }` |
| `GET` | `/api/dashboard/stats/tokens` | `dashboard:view` | `granularity=day`（仅 `week` 按周；其它值含默认 `day` 按日） | `{ granularity, trend[], response_time_distribution[] }` |

与 `/api/metrics/*` 不同：Dashboard 是**业务运营**指标；Metrics 是进程内图任务可观测性。

---

## Settlement

前缀：`/api/settlement`。均需 `settlement:manage`。

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `GET` | `/api/settlement/faqs/recommendations` | `settlement:manage` | `refresh=false`：为 `true` 时重挖推荐，否则读已存推荐 | `{ items }` |
| `GET` | `/api/settlement/faqs` | `settlement:manage` | `status=published`；亦支持 `pending_review` | `{ items }`（待审≈推荐列表，已发布≈正式 FAQ） |
| `POST` | `/api/settlement/faqs/{faq_id}/review` | `settlement:manage` | body：`action`=`approve`\|`reject`，`edited_answer?` | 更新后的 FAQ |
| `POST` | `/api/settlement/faqs/{faq_id}/cache` | `settlement:manage` | body：`cache_enabled: bool` | 开关 FAQ 命中缓存 |
| `GET` | `/api/settlement/knowledge-gaps` | `settlement:manage` | `refresh=false`；可选 `status` 过滤 | `{ items }` |
| `POST` | `/api/settlement/knowledge-gaps/{gap_id}/status` | `settlement:manage` | body：`status`=`unresolved`\|`resolved`\|`ignored` | 更新后的缺口 |
| `POST` | `/api/settlement/knowledge-gaps/{gap_id}/create-unit` | `settlement:manage` | body：可选 `title`, `content` | 从缺口创建知识单元 |

业务语义：`refresh` **默认 `false`**（与当前代码一致）——列表先读库；显式 `refresh=true` 才触发挖掘。`approve` 可将推荐沉淀为已发布 FAQ；`cache_enabled` 控制 AI 侧是否优先命中该 FAQ。

---

## Metrics

前缀：`/api/metrics`。**无需 JWT**。进程内任务 Trace / 节点耗时（导入图等），非业务看板。

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `GET` | `/api/metrics/overview` | — | — | `total_requests`, `completed`/`failed`/`processing`, `success_rate`, `latency_p*`, `uptime_s` |
| `GET` | `/api/metrics/nodes` | — | — | 按节点名：`count`, `avg_s`, `max_s`, `min_s`, `p50_s` |
| `GET` | `/api/metrics/recent` | — | `limit=20`（≤100） | 最近任务摘要列表 |
| `GET` | `/api/metrics/trace/{task_id}` | — | — | 任务 durations / done_list / running_list；未知任务返回 `{ error, task_id }` |

---

## Health

| 方法 | 路径 | 权限 | 关键参数 | 响应要点 |
|------|------|------|----------|----------|
| `GET` | `/api/health` | — | — | `{ "status": "healthy", "service": "kb-platform" }` |

---

## curl 示例

假设服务监听 `http://127.0.0.1:8000`。种子账号见 `knowledge/auth/seed.py`（如 `admin` / `Admin@123`）。

### 健康检查

```bash
curl -sS http://127.0.0.1:8000/api/health
```

期望：`{"status":"healthy","service":"kb-platform"}`。

### 登录

```bash
curl -sS -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin@123"}'
```

从响应取出 `access_token`。

### 列出知识单元（占位 token）

```bash
TOKEN='<access_token>'

curl -sS 'http://127.0.0.1:8000/api/knowledge/units?page=1&page_size=20' \
  -H "Authorization: Bearer ${TOKEN}"
```

需账号具备 `knowledge:view`（`admin` / `kbadmin` 具备；普通 `user` 角色种子亦含该码）。

---

## 相关

- OpenAPI UI：服务启动后访问 `/docs`
- 应用入口：`knowledge/api/app_main.py`
- 权限种子：`knowledge/auth/seed.py`
