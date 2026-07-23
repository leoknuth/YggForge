# Rules

如果你第一次进入 `knowledge/`，建议先看：

- [../README.md](../README.md)

这里存放稳定、可复用、应被优先遵守的约束。

## 目录

- [建议放什么](#建议放什么)
- [目录层次](#目录层次)
- [相关文档](#相关文档)
- [当前条目](#当前条目)

## 建议放什么

建议优先放：

- 代码风格
- 注释边界
- 路径表达约定
- Git 操作纪律
- 错题本晋升规则

目录深度：相对 `knowledge/` 不超过 5 级（含文件名）。主题域可用子目录（如 `mycapital/`）。

不建议直接放：

- 一次性对话纠错
- 工具实现细节
- 某个 Agent 的临时工作流

新增条目时建议从：

- [../templates/rule.template.md](../templates/rule.template.md)

front matter 必填 `type: rule`；`when_to_read` / `related` 写 YAML。需要 Cursor `alwaysApply` 时设 `always_apply: true` 后跑 `ygg project mdc`。

## 目录层次

允许按**主题 / 组织边界**建子目录，例如：

- `mycapital/`：茂源内部框架相关规则（simu 等）

子目录内可再放 `README.md` 说明该组规则的适用范围。

## 相关文档

- [检索约定](../../../docs/concepts/retrieval-conventions.md)（`tags` / `related` / 联想检索）

## 当前条目

- `agent-coding-discipline.md`
- `comment-boundaries.md`
- `compatibility-defaults.md`
- `cpp-style.md`
- `default-trigger-routing.md`（默认触发路由真源；`always_apply` + 手写薄投影 `profiles/cursor/rules/ygg-default-trigger.mdc`）
- `git-workflow.md`
- `markdown-docs.md`
- `memory-promotion.md`
- `mycapital/simu-libbarraopt-warning.md`
- `mycapital/simu-quote-rate-ignore.md`
- `path-expression.md`
- `performance-checklist.md`
- `python-style.md`
- `secrets-placeholder-boundary.md`
- `seed-tag-language.md`（associate seed tag 语言策略；按需检索，非 alwaysApply）
- `standing-preference.md`（综合回答策略真源；`always_apply` + 手写薄投影 `profiles/cursor/rules/ygg-answer-synthesis.mdc`）
- `troubleshooting-web-search.md`
- `windows-powershell-chaining.md`
- `workspace-format.md`

带 `always_apply: true` 的规则：用 `ygg project mdc` 生成/检查 Cursor `.mdc` 投影（真源后缀仍为 `.md`）。
