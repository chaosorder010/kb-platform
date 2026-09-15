# 知识库管理平台（掌柜智库）

企业级 **知识库管理平台 + RAG 引擎**：登录与组织权限、知识单元生命周期、鉴权问答与运营沉淀在上层；底层仍是 LangGraph 多节点管道、BGE-M3 微调嵌入与混合检索。

- **平台层**：统一 API `knowledge/api/app_main.py`（`/api/*`，默认 :8000）+ React 管理前端 `frontend/`（Vite + Ant Design）
- **引擎层**：文档智能导入、语义检索、联网搜索增强、SSE 流式回答；端到端可观测（LangFuse / 指标）

更多入口：API 参考 [`docs/api.md`](docs/api.md)；需求与改造 SSOT [`docs/spec/改造计划/`](docs/spec/改造计划/)。

---

## 平台功能

| 能力 | 说明 |
|---|---|
| **登录 / 鉴权** | JWT 登录；按角色权限码控制菜单与接口 |
| **组织** | 部门、用户、角色与权限配置 |
| **知识单元** | 文档导入、版本/附件、单元级权限（谁可问哪份知识） |
| **鉴权问答** | AI 对话走权限过滤检索；无权限时返回可申请的知识卡片 |
| **看板** | 问答/知识单元排行、Token 等运营指标 |
| **FAQ / 知识缺口** | 沉淀页：FAQ 推荐审核与发布、知识缺口处理（建单元 / 忽略） |

演示角色见下方「使用流程」中的种子账号。

---

## 核心亮点

- **管理平台闭环**：组织 → 知识单元 → 权限问答 → 看板 / FAQ / 缺口沉淀
- **BGE-M3 嵌入模型微调**：60 条训练样本，Recall@1 从 47% 提升至 95%，MRR 从 0.61 提升至 0.97
- **多路混合检索**：稠密向量 + 稀疏向量双路召回 → RRF 融合 → BGE-Reranker 精排 → 动态断崖截断
- **MCP 协议联网搜索**：对接阿里云 DashScope WebSearch，检索结果与本地知识库融合
- **多轮对话 + 指代消解**：MongoDB 持久化历史，支持"这个"→具体商品名消解
- **VLM**：导入期自动识别文档图片生成中文摘要；查询管道含图片理解节点（当前 React AI 页为纯文本；旧 `knowledge/front/chat.html` 依赖未挂载的 `query_router`，不能对当前统一入口直接用）
- **SSE 流式输出**：支持非流式与流式两种模式
- **端到端可观测性**：LangFuse 全链路 Trace、JSON 结构化日志、看板与 `/api/metrics/*`

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│  frontend/  React + Vite + Ant Design  :5173         │
│  登录 / 组织 / 知识库 / AI / 看板 / 沉淀              │
│  开发代理 /api → 统一后端（可配端口与目标）            │
└──────────────────────────┬──────────────────────────┘
                           │
              统一 API :8000  knowledge/api/app_main.py
         auth · org · knowledge · ai · dashboard ·
              settlement · metrics
                           │
           ┌───────────────┴───────────────┐
           │                               │
     LangGraph 查询管道              LangGraph 导入管道
           │                               │
     ┌─────┼──────────────┬────────────────┤
     │     │              │                │
  Milvus  MongoDB    DashScope    MinIO   LangFuse
```

---

## 技术栈

| 层次 | 技术 |
|---|---|
| **编排框架** | LangGraph（状态图驱动多节点管道） |
| **LLM 服务** | 阿里云 DashScope（qwen-flash / qwen3-vl-flash），OpenAI 兼容接口 |
| **嵌入模型** | BGE-M3（微调版），混合稠密+稀疏向量，FlagEmbedding + PyMilvus |
| **重排序** | BGE-Reranker-v2-m3（FlagEmbedding） |
| **向量数据库** | Milvus 2.5.x（混合检索 + COSINE/IP 度量） |
| **对话 / 业务数据** | MongoDB（会话、组织、知识单元与沉淀等） |
| **对象存储** | MinIO（原始文件持久化） |
| **PDF 解析** | MinerU（PDF → Markdown，支持表格、公式） |
| **Web 框架** | FastAPI + Uvicorn + SSE 流式推送 |
| **MCP 协议** | openai-agents + MCPServerStreamableHttp（DashScope WebSearch） |
| **可观测性** | LangFuse 全链路追踪 + JSON 结构化日志 |
| **前端** | React + Vite + Ant Design（`frontend/`） |

---

## 项目结构

```
kb-platform/
├── frontend/                           # React 管理前端（登录/组织/知识库/AI/看板/沉淀）
├── knowledge/                          # 平台 API + RAG 引擎
│   ├── api/
│   │   ├── app_main.py                 # 统一入口（:8000）；挂载下列 router → /api/*
│   │   ├── auth_router.py              # /api/auth/*
│   │   ├── org_router.py               # /api/org/*
│   │   ├── knowledge_router.py         # /api/knowledge/*（导入、单元、权限）
│   │   ├── ai_router.py                # /api/ai/*（鉴权流式问答、历史）
│   │   ├── dashboard_router.py         # /api/dashboard/*
│   │   ├── settlement_router.py        # /api/settlement/*（FAQ、知识缺口）
│   │   ├── metrics_router.py           # /api/metrics/*
│   │   ├── import_router.py            # 遗留：/api/upload|/api/status（未在 app_main 挂载）
│   │   └── query_router.py             # 遗留：/api/query|/api/stream|/api/history（未挂载）
│   ├── auth/                           # 密码、种子用户与权限码
│   ├── core/ / processor/ / service/   # 配置、管道、业务层
│   ├── front/                          # 旧 HTML 页面（含查询期图片提问）
│   └── test/
├── eval/                               # 模型评估与微调
└── docs/                               # API、agents、spec、联调报告
```

当前问答与导入以 `knowledge_router` / `ai_router` 为准；`import_router` / `query_router` 保留作遗留参考，不再作为统一入口路径。

---

## 导入管道（Import Pipeline）

文档导入经过 7 个 LangGraph 节点的状态图管道：

| 节点 | 功能 | 核心技术 |
|---|---|---|
| **entry_node** | 判断文件类型（PDF/MD），路由分支 | 文件扩展名检测 |
| **pdf_to_md_node** | PDF 转 Markdown | MinerU CLI（子进程调用） |
| **md_to_img_node** | 提取 MD 中引用的图片，VLM 生成摘要 | Qwen-VL（base64 编码图片） |
| **document_split_node** | 文档切片（基于 Markdown 标题层级） | 自定义 Markdown Splitter |
| **item_name_recognition_node** | LLM 提取商品名称型号 | Qwen-Flash + Prompt Engineering |
| **embedding_chunks_node** | BGE-M3 批量生成稠密+稀疏向量 | BGEM3FlagModel（CUDA） |
| **import_milvus_node** | 向量及元数据写入 Milvus | MilvusClient（HYBRID 集合） |

---

## 查询管道（Query Pipeline）

用户提问经 LangGraph 状态图：业务节点如下表（另有虚节点 `multi_search` / `join` 做三路并行汇合；SSE 在 `answer_output_node` 内推送）。首节点为图片理解，无图时透传：

| 节点 | 功能 | 核心技术 |
|---|---|---|
| **image_understanding_node** | 用户上传图片理解（无图透传） | Qwen-VL 生成描述拼进 query + MinIO 存图 |
| **item_name_confirmed_node** | 提取/确认商品名 + 问题改写 + 指代消解 | LLM + 对话历史 |
| **hybrid_vector_search_node** | 稠密+稀疏混合向量检索 | Milvus hybrid_search + 商品名过滤 |
| **hyde_vector_search_node** | HyDE（假设文档嵌入）增强检索 | LLM 生成假设文档 → BGE-M3 嵌入 → 检索 |
| **web_mcp_search_node** | MCP 协议联网搜索 | DashScope WebSearch |
| **rrf_merge_node** | RRF（倒数排序融合）多路结果 | Reciprocal Rank Fusion |
| **reranker_node** | BGE-Reranker 精排 + 动态断崖截断 | FlagReranker + sigmoid 归一化 |
| **authz_filter_node** | 按知识单元数据权限过滤召回结果 | unit_id ↔ 用户权限；缺失卡片 |
| **answer_output_node** | 上下文组装 + LLM 生成答案 + SSE 推送 | Qwen-Flash + 对话历史注入 |

> 查询期带图：管道节点已支持；React AI 页当前纯文本。旧 HTML 聊天页依赖未挂载的 `query_router`，勿当作现行入口。

---

## BGE-M3 微调效果

| 指标 | 原始模型 | 微调后 | 提升 |
|---|---|---|---|
| **Recall@1** | 46.7% | **95.0%** | +48.3% |
| **Recall@3** | 66.7% | **98.3%** | +31.7% |
| **Recall@5** | 83.3% | **100.0%** | +16.7% |
| **MRR** | 0.614 | **0.971** | +58.1% |
| **平均排名** | 3.18 | **1.08** | -2.10 |

- 训练数据：60 条 QA + 180 条难负例
- 方法：LoRA 微调（target_modules=["query","key","value","dense"]）
- 60 条问题无退化，53% 进一步提升

---

## 快速开始

### 环境要求

- Python 3.12+
- CUDA GPU（推荐 RTX 2060 6GB 及以上）
- Docker（用于运行 Milvus、MinIO、MongoDB）

以下命令默认在**仓库根目录** `kb-platform/` 执行（除非另行标明）。

### 1. 安装依赖

```bash
pip install -r knowledge/requirements.txt
pip install FlagEmbedding transformers torch
```

也可先 `cd knowledge` 再装 `requirements.txt`，但后续 Docker / 后端启动请回到仓库根。

### 2. 配置环境变量

复制 `knowledge/.env.example` 为 `knowledge/.env` 并编辑。本机 Docker Compose 常用值示例：

```ini
# LLM API（阿里云 DashScope）
OPENAI_API_KEY=***
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DEFAULT_MODEL=qwen-flash
VL_MODEL=qwen3-vl-flash

# BGE 模型路径（按本机实际路径修改）
BGE_M3_PATH=.../eval/finetuned_bge_m3/merged
BGE_RERANKER_LARGE=.../models/bge-reranker-v2-m3
BGE_DEVICE=cuda:0
BGE_FP16=True

# 中间件（与 docker-compose.yml 默认一致；远端部署时改 IP）
MILVUS_URL=http://127.0.0.1:19530
CHUNKS_COLLECTION=kb_chunks_v1
ITEM_NAME_COLLECTION=kb_item_names_v1
MONGO_URL=mongodb://admin:123456@127.0.0.1:27017
MONGO_DB_NAME=kb001
MINIO_ENDPOINT=127.0.0.1:9000

MCP_DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://127.0.0.1:3000
LANGFUSE_PUBLIC_KEY=pk-xxxxx
LANGFUSE_SECRET_KEY=sk-xxxxx
```

### 3. 启动基础服务（Docker Compose）

```bash
# 在仓库根目录
docker compose up -d
```

### 容器访问地址总览

| 服务 | 地址 | 说明 |
|---|---|---|
| **Attu**（Milvus 管理） | `http://localhost:7000` | Milvus 图形化管理界面 |
| **MinIO Console** | `http://localhost:9001` | 对象存储管理 |
| **LangFuse** | `http://localhost:3000` | LLM 可观测性平台（Trace/Token/成本） |
| **统一 API** | `http://localhost:8000` | `GET /api/health` |
| **前端开发服** | `http://localhost:5173` | 默认端口；可用 `VITE_DEV_PORT` 覆盖 |

### 4. 启动应用

```bash
# 终端 1 — 统一后端（仓库根）
PYTHONPATH=. python -m knowledge.api.app_main
# → http://localhost:8000/api/health

# 终端 2 — 前端
cd frontend
npm install
# VITE_DEV_PORT=5174 VITE_API_TARGET=http://127.0.0.1:8000 npm run dev
npm run dev
# → http://localhost:5173（或 VITE_DEV_PORT 指定端口）
```

`frontend/vite.config.ts` 已支持：

- `VITE_DEV_PORT`：开发服务器端口（默认 `5173`）
- `VITE_API_TARGET`：`/api` 代理目标（默认 `http://127.0.0.1:8000`）

### 5. 使用流程

1. 启动统一后端与前端开发服，打开前端地址（默认 `http://localhost:5173`）
2. **登录**（种子账号，见 `knowledge/auth/seed.py`）：

   | 用户名 | 密码 | 角色 |
   |---|---|---|
   | `admin` | `Admin@123` | 系统管理员（组织 + 全菜单） |
   | `kbadmin` | `Kb@123456` | 知识管理员（知识库 / AI / 看板 / 沉淀） |
   | `alice` | `User@123` | 普通用户（AI 问答） |
   | `bob` | `User@123` | 普通用户（AI 问答） |

3. **导入**：知识库页上传 PDF/MD，跟踪导入任务；编辑单元可配附件与版本
4. **配权限**：在知识单元上配置可见范围，再以普通用户验证鉴权问答
5. **问答**：AI 对话页多轮提问（SSE）；无权限时会提示相关知识卡片
6. **看板 / 沉淀**：看板看排行与 Token；沉淀页审核 FAQ、处理知识缺口

健康检查：`GET http://localhost:8000/api/health`

---

## 关键设计

### 客户端单例模式

所有 AI 和存储客户端采用**双重检查锁**单例模式，避免重复初始化模型和数据库连接：

```python
@classmethod
def _get_or_create(cls, attr_name, lock, factory):
    instance = getattr(cls, attr_name, None)
    if instance is not None:
        return instance
    with lock:
        if getattr(cls, attr_name, None) is None:
            setattr(cls, attr_name, factory())
    return getattr(cls, attr_name)
```

### 动态 Top-K 断崖截断

Reranker 精排后不是固定取 Top-K，而是通过 sigmoid 归一化分数，在排序结果中寻找相邻文档间的**最大分数断崖**（gap ≥ 0.15），在断崖处截断，兼顾相关性和噪声过滤。

### HyDE（假设文档嵌入）

用户问题先让 LLM 生成一段"假设的技术文档片段"，再用 BGE-M3 对该片段做向量检索。这种方法对口语化、不规范的查询有显著提升效果。

### MCP 联网搜索降级

联网搜索采用 `MCPServerStreamableHttp` 协议对接 DashScope WebSearch，失败时优雅降级为仅本地检索，不影响核心功能。

---

## 后续规划

按优先级分档，P0 为最该补齐的评测与质量闭环。

### P0 · 评测与质量闭环

- [ ] 端到端 ragas 评测：跑 Faithfulness / Answer Relevancy / Context Precision / Context Recall / Answer Correctness 五指标，配 LLM-as-Judge 做错误分类，补齐答案层量化指标（当前仅有检索层 Recall / MRR）
- [ ] 反思迭代闭环：Reranker 后增加 Reflection 节点，LLM 判断上下文是否充分回答，不足则改写 query 回流检索（最多 N 轮），从单轮 RAG 升级为 Agentic RAG

### P1 · 模型层与工程深化

- [ ] 生成模型 QLoRA 微调 + vLLM 私有化部署：用现有管道蒸馏引用式答案 SFT 数据，微调 Qwen2.5-7B 替换 qwen-flash API，降低延迟与 token 成本
- [ ] 语义缓存：Redis 向量缓存高频 query 的 rerank 结果 / answer，命中即返回
- [ ] Query 路由 / 意图分流：事实型问题走轻量检索，多跳问题走 HyDE + 反思，闲聊直连 LLM，降低平均延迟

### P2 · 能力扩展

- [x] 查询期图片理解（管道 + 旧 HTML）：用户图 → Qwen-VL 描述拼进 query → 复用检索；用户图可存 MinIO
- [ ] React AI 页暴露图片上传 / 粘贴（对齐管道能力）
- [ ] 知识图谱集成：实体关系抽取 + GraphRAG，增强多跳推理
- [ ] Agent 工具调用体系：ReAct + 自定义 Tool + MCP 网关，支持查库存 / 订单等外部动作而非仅文档检索

### P3 · 工程化与运维

- [ ] 测试体系：pytest 覆盖节点级单测 + 管道集成测试
- [ ] 应用容器化：Dockerfile 打包统一 API / 前端（当前仅基础设施容器化）
- [ ] 依赖锁文件：requirements.lock / poetry.lock
- [x] `.env.example` 模板（`knowledge/.env.example`）
- [ ] 安全加固：确保 `.env` 不入库并轮换密钥

### 已完成

- [x] Docker Compose 一键部署（Milvus / MinIO / MongoDB / etcd / Attu / LangFuse）
- [x] 端到端可观测性（LangFuse 全链路追踪 + 看板 / metrics + JSON 结构化日志）
- [x] 管理平台：登录鉴权、组织（部门/用户/角色）、知识单元导入与权限、鉴权 AI 问答
- [x] 运营沉淀：看板指标、FAQ 推荐审核与发布、知识缺口处理
