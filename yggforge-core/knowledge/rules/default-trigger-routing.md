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
last_reviewed: 2026-11-06
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

- 有 hooks 的环境使用与本轮会话、消息匹配且未过期的检测结果；不复用旧消息或其他会话的结果。
- `beforeSubmitPrompt` 在消息提交前检测意图，按会话与消息隔离保存；回答前通过验证入口核对身份、原文摘要与时效。共享的 `last_trigger.json` 不作为可信路由输入。
- `sessionStart` 提供路由引导；注入是否成功不替代检测结果验证。无 hook 或无法获得匹配身份时，按本轮 AGENTS 约定判断或重新检测，不猜测缓存所属消息。
- 开关：`behavior.defaults.yaml` / `behavior.local.yaml` 的 `features.default_trigger_on_chat`（部署默认 `true`）。
- 是否真正执行各命令由对应 behavior 门禁（ask/allow/deny）决定。
- 与综合回答策略并行：见 `standing-preference.md` / `ygg-answer-synthesis.mdc`。
- seed tag 语言策略见 `seed-tag-language.md`（associate 路径内嵌引用）。

完整约定：`docs/reference/triggers.md`、`docs/reference/behavior-config.md`。

## Non-goals

- 不替代各命令自身的 behavior 门禁。
- 不把 profile 专用钩子实现细节写进本规则正文（实现在 `profiles/cursor/hooks/`）。
