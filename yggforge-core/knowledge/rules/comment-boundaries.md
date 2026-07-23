---
id: 20260701165030-kr$$$$-cb$$$$$$-qppv
title: Comment Boundaries
type: rule
status: active
confidence: high
source: agent-profile
scope: Source code comments and explanatory docstrings
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - comments
  - docs
  - provenance
keywords:
  - 注释来源
  - 外部血统
  - provenance
related:
  - 20260701165030-kr$$$$-peb$$$$$-k9e1
priority: medium
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及代码注释、docstring、来源说明、是否要在注释中提外部仓库时优先加载
---
# Comment Boundaries

代码注释只说这些内容：

- 当前仓库中这段代码做什么
- 为什么这样写
- 调用方或维护者需要注意什么

默认不要在注释里写：

- “从某项目拷贝”
- “对齐某某仓库”
- 其他外部仓库、外部产品或外部路径来源

如果需要追溯来源，应放到：

- 设计文档
- 提交信息
- issue / ADR / 参考资料条目

## Applies To

- 源代码注释
- 说明性 docstring

## Not For

- 正式设计文档
- 参考资料归档
