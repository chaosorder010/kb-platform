# 知识库管理平台

企业级知识库管理平台 + RAG 引擎。说明见 `README.md`；API 见 `docs/api.md`。

## Context pointers

**Issue tracker** — GitHub `chaosorder010/kb-platform`；CLI 约定见 `docs/agents/issue-tracker.md`。

**Domain** — 探索代码前读 `CONTEXT.md` 与相关 `docs/adr/`（lazy 创建见 `docs/agents/domain.md`）。

**Spec** — 需求与改造 SSOT：`docs/spec/改造计划/`。

**联调** — 端到端结论：`docs/reports/联调报告.md`。

**Docs** — `docs/` 只留唯一信息与索引；逻辑在代码里则指向代码；改代码时同步更新文档。

## Workflow

### 1. Align

1. 先读相关代码与上述 context，再问清缺口信息。
2. 给出方案，等人类确认后再改代码。

完成：人类已确认方案（只读或仅改文档的任务除外）。

### 2. Build

1. **TDD**：先写测再实现；单测触及下一层依赖，更深才 mock。
2. 模块完成后用真实资源走真实用户路径验证。
3. 只跑触及变更的测试；全量测试留到上线部署前。
4. 代码始终 **green**（可编译、可运行）。
5. 临时设计稿放 `.tmp/docs/`，用完即弃。
6. 产出保持 **stateless deliverable**：可直接交付，不含过程性修改说明。
7. 文档随代码更新，只写索引与唯一信息。

完成：真实路径验证通过，触及测试 green，文档与代码同向。

### 3. Ship

1. **surgical review**：架构分叉、职责、历史包袱、过度兜底、无复用价值的 helper、过程性说明——该删删、该合合。
2. 人类允许并完成 Code Review 后，再按独立可回滚变更 commit；每次 commit 保持 green。

完成：人类确认可 commit，且 HEAD green。

## Principles

决策挂在 leading words 上；同一含义只在此处定义一次。

- **long-term** — 每个改动降低未来成本；默认不留兼容与历史包袱；不计 AI 编码的人工成本，选长期最佳路径。
- **SSOT** — 写入口唯一，其余派生复用；相同类型同源定义。
- **read-first** — 先读后写；优先复用/扩展现有代码；成熟库能解决就不造轮子。
- **iterate** — 迭代改写，不堆叠补丁；重写后删旧；顺手清掉不符原则的代码。
- **KISS** — 最短且长期最佳；架构冗余就简化；结构统一，避免分叉。
- **deep module** — 复杂度封在组件内，对外只留必要生命周期与 API。
- **surgical** — 结构性问题用重构；修 bug 找 **root cause**，用正确逻辑修。
- **strong types** — 合适强度的强类型；OO 为主、函数为辅。
- **real** — 只做真实生效的改动。
- **self-describing** — 代码自解释，不写注释。
- **no one-shot helpers** — 不写仅单次调用、无抽象价值的私有 helper。
- **foundation tax** — 新功能约三分之一改动用于基础架构/组件升级。
- **2000-line file** — 超限则按职责、层次、领域边界做结构审查并拆分。
- **UI restraint** — 前端少描述性文案与边框线。
- **schema** — 数据库变更遵循既有表设计与项目约定。
- **private secrets OK** — 私有仓可放密钥；法律/合规提醒从简，后续用合规手段处理。


# codegraph
本项目使用codegraph cli/mcp 访问代码图
