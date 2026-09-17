# 文档结构

本项目的长期文档结构。

## 顶层目录

- `docs/spec/`：产品行为、API 契约、面向用户的需求和功能契约。
- `docs/test/`：测试策略、覆盖率记录、回归用例和手工验证记录。
- `docs/arch/`：架构决策、代码约定、模块边界、数据流、基础设施与运行时依赖、集成边界和迁移设计。
- `docs/plan/`：本地活动实现计划。
- `docs/archive/`：本地已完成计划、历史记录、载荷记录和调查记录。

## 命名

- `docs/` 下的目录使用 kebab-case。
- `docs/` 下的 Markdown 文件使用 UPPER_SNAKE_CASE。
- `README.md` 是唯一允许混合大小写的 Markdown 文件名例外，并且用于索引或概览文件。

## 文件大小建议

单个文件尽量控制在 200 行和 10,000 个字符以内。超过任一限制时，应拆分为职责聚焦的文件，并让 `README.md` 保持为索引或概览。配置的校验例外应保持范围明确且有意为之。

## README 索引

每个 docs 子目录的 `README.md` 都是该目录的本地目录。它应列出重要文件、任务目录、状态，以及每个条目的单行用途说明。

新增、重命名、拆分、移动或归档文档时，应在同一变更中更新最近的相关 `README.md`。

## 领域目录升级

从单个聚焦的 Markdown 文件开始。当一个领域增长为多个文档时，将其提升为 `docs/<area>/<domain>/README.md`，并在该目录中放置相关的 UPPER_SNAKE_CASE Markdown 文件。

## 规格说明撰写约定

行为规格描述当前的产品契约，包括支持的命令、API 形状、面向用户的行为、默认值、约束和校验结果。

规格说明不应描述行为如何随时间变化。应将历史变更表述改写为直接的当前状态规则。历史背景、迁移理由、未来扩展想法和已完成计划的说明，应放入 `docs/arch/`、`docs/test/`、`docs/archive/` 或活动中的 `docs/plan/` 文件。如果兼容行为仍对用户可见，则应保留在规格说明中，但要表述为当前支持或不支持的规则。

当 `remove`、`exclude`、`fallback` 和 `replacement semantics` 等配置或操作术语能够精确描述当前行为时，可以使用它们。

## 可追溯性区块

行为规格可以在末尾包含 fenced `json dotdotgod` 可追溯性区块，用于连接规格、源代码、测试、相关文档和验证命令。schema 和校验行为由 dotdotgod CLI 负责。

## 计划与归档目录

活动任务计划使用 `docs/plan/<task-slug>/README.md`。已完成或被替代的计划任务目录移动到 `docs/archive/plan/<task-slug>/`。临时调查、报告、载荷记录和历史记录放在 `docs/archive/report/<report-slug>/`。

`docs/plan` 和 `docs/archive` 默认被 Git 忽略。
