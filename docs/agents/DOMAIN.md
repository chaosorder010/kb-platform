# 领域文档

工程技能探索代码库时，应按以下方式使用本项目的领域文档。

## 开始探索前，先阅读以下内容

- 仓库根目录的 **`CONTEXT.md`**，或
- 如果根目录存在 **`CONTEXT-MAP.md`**，先阅读它指向的、与当前主题相关的各个 `CONTEXT.md`。
- 阅读涉及当前工作范围的 **`docs/adr/`** 中的 ADR。在多上下文仓库中，也要检查 `src/<context>/docs/adr/` 下与具体上下文相关的决策。

如果这些文件不存在，请静默继续。不要专门提示它们缺失，也不要在前期建议创建它们。`/domain-modeling` skill 会在术语或决策真正确定时按需创建这些文件。

## 文件结构

单一上下文仓库（大多数仓库）：

```
/
├── CONTEXT.md
├── docs/adr/
│   ├── 0001-event-sourced-orders.md
│   └── 0002-postgres-for-write-model.md
└── src/
```

多上下文仓库（根目录存在 `CONTEXT-MAP.md`）：

```
/
├── CONTEXT-MAP.md
├── docs/adr/                          ← 系统级决策
└── src/
    ├── ordering/
    │   ├── CONTEXT.md
    │   └── docs/adr/                  ← 上下文级决策
    └── billing/
        ├── CONTEXT.md
        └── docs/adr/
```

## 使用术语表中的词汇

当输出中需要命名领域概念时，例如 issue 标题、重构提案、假设或测试名称，应使用 `CONTEXT.md` 中定义的术语。不要改用术语表明确避免的同义词。

如果需要使用的概念尚未出现在术语表中，这意味着你可能正在发明项目尚未使用的语言，应重新考虑，或者记录这是 `/domain-modeling` 需要补充的领域缺口。

## 标记 ADR 冲突

如果输出与已有 ADR 冲突，应明确指出，不要静默覆盖：

> _与 ADR-0007（事件溯源订单）冲突，但值得重新讨论，因为……_
