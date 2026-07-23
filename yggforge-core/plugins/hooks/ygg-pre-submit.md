---
id: ygg-hook-pre-submit
title: YggForge 根钩子 beforeSubmitPrompt
title_refined: ygg pre-submit hook
type: hook
status: active
confidence: high
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - ygg
  - trigger
  - cursor
  - hooks
agent_targets:
  - cursor
event: beforeSubmitPrompt
command_ref: profiles/cursor/hooks/ygg_pre_submit.py
trigger_tags:
  - ygg
  - trigger
timeout: "10s"
depends_on: []
project_to:
  cursor: ~/.cursor/hooks.json:hooks.beforeSubmitPrompt
---
# YggForge 根钩子

## 作用

`beforeSubmitPrompt` 是 YggForge 的 **bootstrap 根钩子**：在每条用户消息提交前
由 Cursor 自动运行 `scripts/hooks/trigger_detector.py`，把检测结果
（`should_trigger` + `action`）落盘到 `yggforge-runtime/cache/last_trigger.json`。

agent 回答前必须先 Read 该文件并按 `action` 路由（见 `ygg-router` 技能）。

## 安装

随 `ygg deploy link cursor` 一次性安装到用户级 `~/.cursor/hooks.json` +
`~/.cursor/hooks/`。安装后 YggForge 内部自成体系，无需再为每个 Agent 重复装钩子。

## 设计原则

- **只装一个根钩子**：所有 ygg 路由靠这一个钩子 + AGENTS.md 读规则约定触发，
  不为每类功能各装一个钩子。
- **不与外部 Agent 自身 hooks 冲突**：YggForge 内部 hooks 体系独立；
  对外只暴露这一个根钩子作为入口。
- **fail open**：检测步骤已硬性下沉到钩子；agent 不得凭自身判断跳过检测，
  但读不到 `last_trigger.json` 时跳过 ygg 检索并继续作答。

## 相关

- 技能：`ygg-skill-ygg-router`
- 真源：`knowledge/rules/default-trigger-routing.md`
- 实现：`profiles/cursor/hooks/ygg_pre_submit.py`、`ygg_session_protocol.py`
