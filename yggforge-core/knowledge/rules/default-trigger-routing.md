---
id: 20260723114000-kr$$$$-d$$$$$$$-trgr
title: 对话默认触发 ygg 路由（强制钩子）
title_refined: 默认触发路由协议真源
type: rule
status: active
confidence: high
source: docs/reference/triggers.md
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - ygg
  - trigger
  - hooks
  - cursor
related:
  - 20260722222018-kr$$$$-y$$$$$$$-ygux
  - 20260722225400-kr$$$$-s$$$$$$$-tgln
when_to_read:
  - Cursor 会话开始或回答任何用户消息之前
  - 部署 / 调整 ygg 强制钩子或 default_trigger_on_chat 时
always_apply: true
projection_mode: manual
projection:
  - profiles/cursor/rules/ygg-default-trigger.mdc
---
# 对话默认触发 ygg 路由（强制钩子）

## Rule

- 检测与路由步骤由 Cursor hooks **硬性执行**，agent 不得凭自身判断跳过。
- `beforeSubmitPrompt`（`ygg_pre_submit.py`）在每条用户消息提交前跑 `trigger_detector`，结果写入 `yggforge-runtime/cache/last_trigger.json`。
- `sessionStart`（`ygg_session_protocol.py`）注入完整路由协议；回答前必读 `last_trigger.json` 并按 `action` 路由。
- 开关：`behavior.defaults.yaml` / `behavior.local.yaml` 的 `features.default_trigger_on_chat`（部署默认 `true`）。
- 是否真正执行各命令由对应 behavior 门禁（ask/allow/deny）决定。
- 与综合回答策略并行：见 `standing-preference.md` / `ygg-answer-synthesis.mdc`。
- seed tag 语言策略见 `seed-tag-language.md`（associate 路径内嵌引用）。

完整约定：`docs/reference/triggers.md`、`docs/reference/behavior-config.md`。

## Non-goals

- 不替代各命令自身的 behavior 门禁。
- 不把 profile 专用钩子实现细节写进本规则正文（实现在 `profiles/cursor/hooks/`）。
