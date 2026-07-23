---
id: 20260701231701-kr$$$$-acd$$$$$-e3p8
title: Agent Coding Discipline
type: rule
status: active
confidence: high
source: "https://github.com/multica-ai/andrej-karpathy-skills"
scope: Global behavioral constraints for AI coding agents
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - agent
  - coding
  - discipline
keywords:
  - think before coding
  - simplicity first
  - surgical changes
  - goal-driven execution
related:
  - 20260701165030-kr$$$$-gwfaa$$$-rjdq
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及一般性编码行为、改动边界、计划方式、是否过度设计时优先加载
non_goals: Does not replace project-specific technical rules
---
# Agent Coding Discipline

## 1. Think Before Coding

- 不要静默假设
- 如果有歧义，先说出可能解释，再决定是否继续
- 如果更简单的方案存在，应主动指出
- 如果真的不清楚，就停下并说明不清楚的点

## 2. Simplicity First

- 只写解决当前问题所需的最小代码
- 不为单次使用场景引入额外抽象
- 不引入用户没要求的“灵活性”或“可配置性”
- 不为不可能发生的场景堆额外错误处理

判断标准：

- 如果一个资深工程师会说“这过度设计了”，那就继续简化

## 3. Surgical Changes

- 只改必须改的部分
- 不顺手改相邻代码、注释、格式
- 不重构没坏的东西
- 发现无关的死代码，可以说明，但不要擅自删除

额外要求：

- 如果你的改动让某些 import / 变量 / 函数变成无用，应清理你自己制造的残留
- 不主动清理历史残留，除非用户要求

判断标准：

- 每一行改动都应能追溯到用户请求

## 4. Goal-Driven Execution

- 不要只接收命令式要求
- 尽量把任务转成可验证的目标

例如：

- “修 bug” -> “先构造能复现 bug 的验证，再让验证通过”
- “加校验” -> “覆盖无效输入场景，并使其通过”
- “重构” -> “确保前后验证结果一致”

对于多步任务：

- 可以先写一个短计划
- 每步都对应一个验证点

## 适用范围

这条规则适合作为：

- 全局 Agent 行为基线
- `render` 的高价值素材
- 多项目共享的最小行为约束

## 不替代的内容

这条规则不替代：

- 具体语言风格规则
- 业务领域规则
- 项目特定测试与提交流程

## Applies To

- 多项目共享的编码行为基线

## Not For

- 替代具体语言风格规则
- 替代业务领域规则
