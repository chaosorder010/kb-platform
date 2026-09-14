# 知识库管理平台（掌柜智库）

企业级 RAG 智能知识库系统。后端统一入口：`knowledge/api/app_main.py`（`/api/*`，默认 :8000）；前端：`frontend/`（React + Vite + Ant Design）。
基于 **LangGraph 多节点管道** + **BGE-M3 微调嵌入** + **混合检索**，支持文档智能导入、精准语义检索、联网搜索增强。

> **项目级别对标**：独立完成此项目，在二三线互联网 / 传统企业可对标 **P7 ~ P8（技术主管 / 架构师）**，
> 在大厂 AI 应用方向可对标 **P6+ ~ P7**。核心依据：BGE-M3 模型微调、多节点 LangGraph 管道编排、
> 混合检索 + Reranker 精排、MCP 协议集成、多轮对话指代消解、VLM 多模态理解。
>
> **薪资参考（2025~2026 行业水平）**：
>
> - 大厂 P6+：40W ~ 55W / 年
> - 大厂 P7：55W ~ 80W / 年
> - 二三线 P7 ~ P8：45W ~ 70W / 年

---

## 核心亮点

- **BGE-M3 嵌入模型微调**：60 条训练样本，Recall@1 从 47% 提升至 95%，MRR 从 0.61 提升至 0.97
- **多路混合检索**：稠密向量 + 稀疏向量双路召回 → RRF 融合 → BGE-Reranker 精排 → 动态断崖截断
- **MCP 协议联网搜索**：对接阿里云 DashScope WebSearch，检索结果与本地知识库融合
- **多轮对话 + 指代消解**：MongoDB 持久化历史，支持"这个"→具体商品名消解
- **VLM 图片理解**：导入时自动识别文档图片生成中文摘要；查询期支持用户上传/粘贴图片提问（VLM 生成描述拼进 query，用户图存 MinIO 可回溯）
- **SSE 流式输出**：支持非流式（一次性返回）和流式（逐字推送）两种模式
- **端到端可观测性**：LangFuse 全链路 Trace（节点耗时、LLM Token 消耗、检索延迟），JSON 结构化日志，实时指标仪表盘

---

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│  frontend/  React + Vite + Ant Design  :5173         │
│  开发代理 /api → 统一后端                            │
└──────────────────────────┬──────────────────────────┘
                           │
              统一 API :8000  knowledge/api/app_main.py
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
| **向量数据库** | Milvus 3.x（混合检索 + COSINE/IP 度量） |
| **对话历史** | MongoDB（会话持久化、上下文注入） |
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
├── frontend/                           # React + Vite + Ant Design
├── knowledge/                          # 核心知识库模块
│   ├── api/
│   │   ├── app_main.py                 # 统一入口（:8000，挂载 /api/*）
│   │   ├── import_router.py            # 导入路由 → /api/upload|/api/status
│   │   ├── query_router.py             # 查询路由 → /api/query|/api/stream|/api/history
│   │   └── metrics_router.py           # 指标路由 → /api/metrics/*
│   ├── core/ / processor/ / service/   # 配置、管道、业务层
│   ├── front/                          # 旧 HTML 页面
│   └── test/
├── eval/                               # 模型评估与微调
└── 项目环境配置&服务部署指南.md
```

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

用户提问经过 9 个节点的状态图管道（首个节点为图片理解，无图时透传）：

| 节点 | 功能 | 核心技术 |
|---|---|---|
| **image_understanding_node** | 用户上传图片理解（无图透传） | Qwen-VL 生成描述拼进 query + MinIO 存图 |
| **item_name_confirmed_node** | 提取/确认商品名 + 问题改写 + 指代消解 | LLM + 对话历史 |
| **hybrid_vector_search_node** | 稠密+稀疏混合向量检索 | Milvus hybrid_search + 商品名过滤 |
| **hyde_vector_search_node** | HyDE（假设文档嵌入）增强检索 | LLM 生成假设文档 → BGE-M3 嵌入 → 检索 |
| **web_mcp_search_node** | MCP 协议联网搜索 | DashScope WebSearch |
| **rrf_merge_node** | RRF（倒数排序融合）多路结果 | Reciprocal Rank Fusion |
| **reranker_node** | BGE-Reranker 精排 + 动态断崖截断 | FlagReranker + sigmoid 归一化 |
| **answer_output_node** | 上下文组装 + LLM 生成答案 + SSE 推送 | Qwen-Flash + 对话历史注入 |
| (流式) **SSE 推送** | 逐字推送 + 进度事件 | SSEEvent.DELTA / PROGRESS / FINAL |

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

### 1. 安装依赖

```bash
cd knowledge
pip install -r requirements.txt
pip install FlagEmbedding transformers torch
```

### 2. 配置环境变量

复制并编辑 `knowledge/.env`：

```ini
# LLM API（阿里云 DashScope）
OPENAI_API_KEY=***
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DEFAULT_MODEL=qwen-flash
VL_MODEL=qwen3-vl-flash

# BGE 模型路径
BGE_M3_PATH=D:\课程视频\...\eval\finetuned_bge_m3\merged
BGE_RERANKER_LARGE=D:\models\bge-reranker-v2-m3
BGE_DEVICE=cuda:0
BGE_FP16=True

# Milvus
MILVUS_URL=http://192.168.10.140:19530
CHUNKS_COLLECTION=kb_chunks_v1
ITEM_NAME_COLLECTION=kb_item_names_v1

# MongoDB
MONGO_URL=mongodb://admin:password@192.168.10.140:27017
MONGO_DB_NAME=kb001

# MinIO
MINIO_ENDPOINT=192.168.10.140:9000

# MCP 联网搜索
MCP_DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp

# LangFuse 可观测性
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://192.168.10.140:3000
LANGFUSE_PUBLIC_KEY=pk-xxxxx
LANGFUSE_SECRET_KEY=sk-xxxxx
```

### 3. 启动基础服务（Docker Compose）

```bash
# 启动所有基础设施容器（Milvus、MinIO、MongoDB、etcd、Attu、LangFuse）
docker compose up -d
```

### 容器访问地址总览

| 服务 | 地址 | 说明 |
|---|---|---|
| **Attu**（Milvus 管理） | `http://192.168.10.140:7000` | Milvus 图形化管理界面 |
| **MinIO Console** | `http://192.168.10.140:9001` | 对象存储管理 |
| **LangFuse** | `http://192.168.10.140:3000` | LLM 可观测性平台（Trace/Token/成本） |
| **统一 API** | `http://localhost:8000` | `GET /api/health` |
| **前端开发服** | `http://localhost:5173` | React 应用 |

### 4. 启动应用

```bash
# 终端 1 — 统一后端
PYTHONPATH=. python -m knowledge.api.app_main
# → http://localhost:8000/api/health

# 终端 2 — 前端
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

### 5. 使用流程

1. 启动统一后端与前端开发服
2. 打开 `http://localhost:5173`
3. 用 `http://localhost:8000/api/health` 确认 API 存活

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

- [x] 多模态深化：查询期图片输入（用户上传/粘贴图片 → Qwen-VL 生成描述拼进 query → 复用三路检索 → 答案可返回文档图片），用户图存 MinIO 可回溯
- [ ] 知识图谱集成：实体关系抽取 + GraphRAG，增强多跳推理
- [ ] Agent 工具调用体系：ReAct + 自定义 Tool + MCP 网关，支持查库存 / 订单等外部动作而非仅文档检索

### P3 · 工程化与运维

- [ ] 测试体系：pytest 覆盖节点级单测 + 管道集成测试
- [ ] 应用容器化：Dockerfile 打包导入 / 查询服务（当前仅基础设施容器化）
- [ ] 依赖锁文件：requirements.lock / poetry.lock
- [ ] 管理后台：文档管理、索引监控
- [ ] 安全加固：.env 移出 git 并轮换密钥、提交 .env.example 模板

### 已完成

- [x] Docker Compose 一键部署（Milvus / MinIO / MongoDB / etcd / Attu / LangFuse）
- [x] 端到端可观测性（LangFuse 全链路追踪 + 指标仪表盘 + JSON 结构化日志）
