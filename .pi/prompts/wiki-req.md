---
description: 使用简体中文捕获并拆解可追踪的原子需求
argument-hint: "<概念描述>"
section: LLM Wiki
topLevelCli: true
---

# /wiki-req

使用简体中文捕获一个概念，并将其拆解为可追踪、可验收的原子需求。

此命令会将自然语言描述转换为结构化的 `wiki/requirements/` 页面，同时将澄清后的原始概念保存为 `raw/sources/` 中的不可变 source packet。

## User Arguments

$ARGUMENTS

Read the LLM Wiki skill at `.pi/skills/llm-wiki/SKILL.md` first to understand the wiki conventions, architecture, and page type rules.

## Language Rules

- 页面标题、需求描述、验收标准、说明和链接别名必须使用简体中文。
- 每个需求调用 `wiki_ensure_page` 时，`title` 必须是简洁明确的中文标题；不要使用 `auth-login-session`、`knowledge-parse-index` 这类英文标识符作为标题。
- `title` 会直接参与生成 Markdown 文件名，因此中文标题会生成中文文件名。
- 代码符号、API 名称、配置项、文件路径、命令、协议名和其他技术专有名词保持原样。
- 页面目录名 `requirements`、frontmatter 字段名、状态值和优先级保持英文，以保证工具解析和链接稳定。
- `raw/` 中的原始来源保持原文，不翻译；写入 `wiki/` 的可编辑知识内容使用简体中文。

## Steps

1. **Clarify the concept**
   - 与用户讨论并拆解含糊术语、隐含假设和范围边界
   - 针对未知信息提出具体问题，例如涉及哪些 provider、fallback 行为是什么、参与者有哪些
   - 在开始拆解前与用户确认概念已经清晰

2. **Capture the clarified concept**
   - 使用 `wiki_capture_source(text=...)`，将澄清后的对话以 Markdown 保存
   - 这会创建 `raw/sources/SRC-YYYY-MM-DD-NNN/`
   - source 保存原始意图，不加入解释，不进行需求拆解

3. **Decompose into atomic requirements**
   - 将概念拆解为最小的有意义功能单元
   - 每条需求只描述一个可以独立验证的行为
   - 对每条原子需求调用一次 `wiki_ensure_page(type="requirement", title="中文需求标题", content="...")`
   - 每个需求页面必须包含：
     - `type: requirement` 和 `status: draft` frontmatter
     - `## Description`，使用简体中文
     - `## Acceptance Criteria`，使用复选框列出完成阈值
     - `source_id`，链接到本次 source capture
     - `depends_on`，链接到前置需求
     - 指向相关实体、概念和其他需求的 `[[wikilinks]]`
   - 根据用户输入设置优先级：`p0`（阻塞）、`p1`（关键）、`p2`（重要）、`p3`（锦上添花）

4. **Cross-link and finalize**
   - 确保每个需求页面与相关页面建立双向 wikilink
   - 更新需求所引用的实体或概念页面
   - 报告创建的需求数量、优先级和 source capture ID

## Rules

- 一次 `wiki_ensure_page` 只创建一条原子需求，每条需求必须可以独立测试
- 必须先使用 `wiki_capture_source` 捕获澄清后的概念，再进行拆解
- 需求页面位于 `wiki/requirements/`，是可编辑 Wiki 页面，不是不可变来源
- 状态值使用：`draft` → `clarified` → `active` → `implemented` → `deferred` → `rejected`
- 优先级使用：`p0`、`p1`、`p2`、`p3`
- 不要在 `raw/` 中创建需求，`raw/` 只保存外部来源资料
- 创建前先使用 `wiki_search` 查重
- 不要重命名或覆盖已有页面；`wiki_ensure_page` 遇到同名页面时应保留现有页面
- Markdown 表格单元格中的别名 wikilink 必须写成 `[[target\|alias]]`，不要写成 `[[target|alias]]`
