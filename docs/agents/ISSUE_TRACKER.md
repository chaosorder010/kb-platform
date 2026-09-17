# GitHub 问题跟踪

本仓库的问题和规格说明以 GitHub Issues 为准。所有操作使用 `gh` CLI。

## 约定

- **创建 issue**：`gh issue create --title "..." --body "..."`。多行正文使用 heredoc。
- **读取 issue**：`gh issue view <number> --comments`，使用 `jq` 过滤评论，并同时获取 labels。
- **列出 issues**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，并按需指定 `--label` 和 `--state`。
- **评论 issue**：`gh issue comment <number> --body "..."`。
- **添加或移除 labels**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`。
- **关闭 issue**：`gh issue close <number> --comment "..."`。

通过 `git remote -v` 推断仓库；在 clone 中执行时，`gh` 会自动完成这一步。

## 将 Pull Request 作为分诊入口

**PR 作为需求入口：否。**（如果外部 PR 也被视为功能需求，请将其设置为 `yes`；`/triage` 会读取此配置。）

设置为 `yes` 后，PR 使用与 issue 相同的 labels 和状态，并采用对应的 `gh pr` 命令：

- **读取 PR**：`gh pr view <number> --comments` 和 `gh pr diff <number>`。
- **列出外部 PR 进行分诊**：`gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`，只保留 `authorAssociation` 为 `CONTRIBUTOR`、`FIRST_TIME_CONTRIBUTOR` 或 `NONE` 的记录，排除 `OWNER`、`MEMBER` 和 `COLLABORATOR`。
- **评论、修改或关闭**：使用 `gh pr comment`、`gh pr edit --add-label` / `--remove-label`、`gh pr close`。

GitHub 的 issue 和 PR 共用同一编号空间，因此单独出现的 `#42` 可能指 issue 或 PR。先执行 `gh pr view 42`，失败后再执行 `gh issue view 42`。

## 当 skill 要求“发布到问题跟踪器”时

创建一个 GitHub issue。

## 当 skill 要求“获取相关工单”时

执行 `gh issue view <number> --comments`。

## Wayfinding 操作

这些操作由 `/wayfinder` 使用。总览是一个单独的 issue，子 issue 作为具体工单。

- **总览**：创建一个带有 `wayfinder:map` label 的 issue，正文包含 Notes / Decisions-so-far / Fog。使用 `gh issue create --label wayfinder:map`。
- **子工单**：将 issue 作为 GitHub sub-issue 关联到总览（通过 sub-issues endpoint 执行 `gh api`）。如果实例未启用 sub-issues，则在总览正文的任务列表中添加子工单，并在子工单正文顶部写入 `Part of #<map>`。label 使用 `wayfinder:<type>`，其中 `<type>` 为 `research`、`prototype`、`grilling` 或 `task`。认领后，将工单分配给负责推进的开发者。
- **阻塞关系**：GitHub 的原生 issue 依赖是规范且可在界面查看的表示方式。使用 `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>` 添加边，其中 `<blocker-db-id>` 必须是阻塞 issue 的数字数据库 id，可通过 `gh api repos/<owner>/<repo>/issues/<n> --jq .id` 获取，不能使用 `#number` 或 `node_id`。GitHub 通过 `issue_dependencies_summary.blocked_by` 报告仍开放的阻塞项，这是实时的放行条件。如果实例不支持依赖关系，则退回在子工单正文顶部写入 `Blocked by: #<n>, #<n>`。只有所有阻塞 issue 都已关闭，工单才算解除阻塞。
- **前沿查询**：列出总览下的开放子工单（使用 `gh issue list --state open`，限定到总览的 sub-issues 或任务列表），排除存在开放阻塞项（`issue_dependencies_summary.blocked_by > 0`，或 `Blocked by` 行中包含开放 issue）或已有 assignee 的工单，按总览中的顺序选择第一个。
- **认领**：`gh issue edit <n> --add-assignee @me`，这是该会话的第一次写操作。
- **解决**：先执行 `gh issue comment <n> --body "<answer>"`，再执行 `gh issue close <n>`，最后将简要结论和链接作为上下文指针追加到总览的 Decisions-so-far。
