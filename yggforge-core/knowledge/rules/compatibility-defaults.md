---
id: 20260714144840-kr$$$$-$$$$$$$$-oq6u
title: 默认实现策略与注释语言
type: rule
status: active
confidence: high
source: agent-profile
scope: 跨项目默认实现偏好与注释语言
last_reviewed: 2026-07-14
owners:
  - team
tags:
  - comments
  - compatibility
keywords:
  - 兼容性
  - 中文注释
  - 默认不保留旧接口
related:
  - 20260701165030-kr$$$$-cb$$$$$$-qppv
  - 20260701163140-kr$$$$-csb$$$$$-vhsf
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 用户提出代码修改但未说明是否要兼容旧接口时
  - 编写或审查注释、docstring 时
always_apply: true
projection_mode: sync
projection:
  - profiles/cursor/rules/compatibility-defaults.mdc
---
# 默认实现策略与注释语言

## Rule

### 代码注释语言

- 所有**你自己编写**的注释（含行内说明、`//`、`#`、块注释与说明性 docstring 中的说明文字）一律使用**简体中文**。
- 不要因注释语言切换而改变代码逻辑。

### 修改默认策略（兼容性边界）

- 当用户提出代码修改需求但**未明确要求兼容性**时，默认以目标实现为准，不主动保留旧接口、旧使用方式、旧命名或额外兼容层。
- 注释与说明仅描述当前实现与设计意图，不回溯旧接口或旧写法。
- 仅当用户明确提出「需要兼容旧版本/旧调用」时，才保留兼容层并在实现中体现。

## Applies To

- 任意语言的代码修改与注释编写

## Not For

- 用户已明确要求兼容旧接口的场景
- 对外公开 API 的 semver 承诺（若用户另行指定）

## Rationale

- 减少默认过度兼容带来的噪音与双轨维护成本
- 注释语言统一便于团队阅读
