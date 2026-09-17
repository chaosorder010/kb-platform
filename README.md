# 知识库管理平台（掌柜智库）

企业级知识库管理平台与 RAG 引擎，提供组织权限、知识单元管理、鉴权问答和运营沉淀能力。

## 项目定位

- 平台层：FastAPI 统一 API，入口为 `knowledge/api/app_main.py`。
- 前端层：React + Vite + Ant Design，位于 `frontend/`；细节见 `frontend/README.md`。
- 引擎层：LangGraph 文档导入与查询管道，使用 Milvus、MongoDB、MinIO 和 DashScope 等基础设施。
- 可观测性：LangFuse 与指标接口。

## 运行入口

前置：Python 3.12+、Docker、Node.js。后端默认 `http://localhost:8000`，健康检查 `GET /api/health`，交互式 OpenAPI 为 `http://localhost:8000/docs`。

```bash
docker compose up -d
# 依赖与环境：见 pyproject.toml、knowledge/requirements.txt、knowledge/.env.example
PYTHONPATH=. python -m knowledge.api.app_main
```

前端默认 `http://localhost:5173`：

```bash
cd frontend
npm install
npm run dev
```

演示账号定义在 `knowledge/auth/seed.py`。

## 项目文档

- `docs/README.md`：文档总索引。
- `docs/spec/`：产品行为、API 契约和需求规格。
- `docs/test/`：测试策略、回归用例和验证记录。
- `docs/arch/`：架构决策、代码约定和模块边界。
- `docs/agents/`：Agent 探索代码库时使用的领域和工单约定。
- `docs/plan/`：本地活动计划，默认不纳入 Git。
- `docs/archive/`：本地完成计划和历史记录，默认不纳入 Git。

## 验证

```bash
dotdotgod validate . --check-index
```

后端测试与前端构建命令分别见 `pyproject.toml` 与 `frontend/package.json`。
