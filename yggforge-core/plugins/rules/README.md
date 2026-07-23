---
id: ygg-plugins-rules-readme
title: plugins/rules 规则包
type: rule
status: active
confidence: high
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - yggforge
  - plugins
  - rules
---
# plugins/rules

YggForge 可投影**规则包**的归属目录（`type: rule`）。

## 定位（第一性原理）

`plugins/rules/` 放的是**可投影到各 Agent 原生 rules 体系的规则包**——即“挑选出来、
要被 `ygg deploy` 投影成 Cursor `.mdc` / Codex `.agents/rules/` 等的规则集合”。

YggForge 自身的**机制规则**（描述 YggForge 如何运作：`default-trigger-routing`、
`standing-preference`、`seed-tag-language`、`secrets-placeholder-boundary`、
`memory-promotion`）**不迁入此处**——它们是被 `trigger_detector` /
`ygg_session_protocol` / 各 profile `AGENTS.md` 按路径引用的**内部操作规程**，
属于知识真源层，留在 `knowledge/rules/`。把内部操作规程塞进“可投影规则包”目录是
类别错误：它们不需要被投影到外部 Agent 的 rules 体系，只需要被 YggForge 自身读取。

> 结论：机制规则留 `knowledge/rules/` 是**正确归属**，不是“暂缓迁移”。
> 本目录预留给将来“挑选出来要投影给 Agent 的规则包”。

## 后续使用准则

- 机制规则（描述 YggForge 自身如何运作）→ 留在 `knowledge/rules/`，被 hooks 按路径读取。
- 领域规则（描述如何做领域工作，如 `cpp-style`、`git-workflow`、`mycapital/*`）→ 留在
  `knowledge/rules/`，继续走晋升模型。
- 可投影规则包（挑选出来要批量投影给某 Agent 的规则集合）→ 放 `plugins/rules/`，
  由 `ygg deploy` 按各 Agent 原生格式投影。
- 任何迁移都同步更新 `trigger_detector.py`、`ygg_session_protocol.py`、各 `AGENTS.md`、
  `docs/` 中的路径引用，并用 `ygg doctor` + `ygg graph check` 验证。

## 与 knowledge/rules 的关系

两者都是 `type: rule`，复用同一 schema，由 `graph_scan` 一并索引。
区别在治理语义：`knowledge/rules/` = 人审晋升的领域规范 + YggForge 内部机制规程；
`plugins/rules/` = 挑选出来要投影给 Agent 的规则包。
