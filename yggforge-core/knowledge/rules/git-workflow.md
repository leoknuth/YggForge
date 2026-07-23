---
id: 20260701165030-kr$$$$-gwfaa$$$-rjdq
title: Git Workflow For AI Agents
type: rule
status: active
confidence: high
source: agent-profile
scope: Agent-assisted repository operations
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - git
  - workflow
  - agent
keywords:
  - git add
  - git commit
  - git push
  - git status
  - push safety
related:
  - 20260701165030-kr$$$$-mapw$$$$-ktcc
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及提交、推送、同步、状态判断、导入回仓库时优先加载
---
# Git Workflow For AI Agents

## 串行纪律

- `git add`
- `git commit`
- `git push`
- `git status`

这些步骤属于强依赖链路，必须串行执行，不要并行化。

## 证据优先

- “无差异”“已提交”“已推送”这类结论必须基于实际命令结果
- 至少用 `git status --short` 或 `git status -sb` 做内部核验
- 不要仅凭预期或口头推断回报 git 状态

## 回报约束

- 默认向用户回报高信息密度摘要，而不是整段原始命令输出
- 若发生 commit，优先回报：
  - 仓库路径
  - commit id
  - 提交标题
  - `git show --stat` 摘要
- `git status` 默认用于内部校验，只有用户明确要求时再展示原始输出

## 提交信息

- 提交标题建议使用 `type(scope): 简要说明`
- 常用 `type` 可为：`feat`、`fix`、`docs`、`refactor`、`chore`
- 提交正文以中文为主，重点说明“为什么做”和“影响范围”

## 安全边界

- 不在提交信息中泄露密钥、密码、token、内网敏感地址
- 对 push 前的权限、保护分支、多人高权限风险检查，应集中在单一流程入口中处理，不要在多个规则里重复写实现细节

## Applies To

- Agent 辅助的仓库操作

## Not For

- 具体业务代码逻辑
