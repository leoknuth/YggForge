---
id: 20260701165030-kr$$$$-peb$$$$$-k9e1
title: Path Expression Boundaries
type: rule
status: active
confidence: high
source: agent-profile
scope: Chat replies, docs, comments, and config files
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - path
  - docs
  - interaction
keywords:
  - 绝对路径
  - 相对路径
  - 项目根
  - path clarity
related:
  - 20260701165030-kr$$$$-cb$$$$$$-qppv
priority: medium
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及路径表达、文档写法、注释写法、配置路径时优先加载
---
# Path Expression Boundaries

## 交互文本

与用户在聊天中沟通时，若提到“项目根/...”之类路径，应优先展开为当前会话可确定的具体绝对路径，避免歧义。

## 持久化内容

在文档、代码注释、配置文件中，默认不要把：

- `项目根`
- `~`
- 相对路径基准

直接展开成机器专属绝对路径。

推荐写法：

- 项目内文档与配置：`项目根/<path>` 或相对路径
- 用户目录相关：`~/.cursor/...`、`~/.codex/...`

## 例外

只有在这些场景才建议写绝对路径：

- 排障日志
- 一次性运维指令
- 用户明确要求精确落盘位置

## Applies To

- 聊天回复
- 文档
- 注释
- 配置文件

## Not For

- 与路径无关的规则条目
