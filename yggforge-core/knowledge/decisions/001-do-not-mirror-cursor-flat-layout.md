---
id: 20260701165030-kd$$$$-d0apc$$$-dy4u
title: "Decision 001: 不镜像 agent-profile 的 Cursor 扁平布局"
type: decision
status: accepted
scope: Knowledge repository structure and multi-agent layout decisions
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - decisions
  - migration
  - structure
  - cursor
keywords:
  - agent-profile
  - flat layout
  - cursor structure
  - knowledge layering
related:
  - 20260701165030-kr$$$$-mapw$$$$-ktcc
priority: medium
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及知识仓库结构、规则分层、是否镜像旧 Cursor 布局时优先加载
consequences_positive:
  - 更适合多 Agent 兼容
  - 更适合后续检索与索引
  - 更容易区分“稳定规范”和“演化中的经验”
  - 更便于以后扩展到非 Cursor 场景
consequences_negative:
  - 迁移时需要重新建立入口与索引
---
# Decision 001: 不镜像 agent-profile 的 Cursor 扁平布局

## Context

参考仓库 `agent-profile` 采用了较强的 Cursor 导向结构：

- `rules/`
- `skills/`
- `tools/`
- `hippocampus/`

这种结构在单工具、内容量较小时很直接，但在多 Agent、知识量增长后会出现几个问题：

- 检索时容易按工具目录而不是按知识语义定位
- 稳定规则与一次性纠错容易混层
- 工具实现细节容易污染知识真源

## Decision

`YggForge` 不镜像该布局作为知识真源。

改为：

- `knowledge/rules/`
- `knowledge/templates/`
- `knowledge/lessons/`
- `knowledge/decisions/`
- `knowledge/sources/`

而工具差异放入：

- `profiles/`
- `scripts/`

## Applies To

- 知识仓库目录设计
- 从旧 Agent 知识系统迁移时的结构取舍

## Not For

- 具体部署命令说明
- 单条规则正文写法
