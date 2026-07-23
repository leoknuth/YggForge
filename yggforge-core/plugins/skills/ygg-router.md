---
id: ygg-skill-ygg-router
title: YggForge 触发路由技能
title_refined: ygg-router skill
type: skill
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
  - routing
  - cursor
agent_targets:
  - cursor
  - codex
  - opencode
  - claude
  - openclaw
depends_on:
  - ygg-hook-pre-submit
project_to:
  cursor: .cursor/skills/ygg-router/SKILL.md
  codex: .agents/skills/ygg-router/SKILL.md
  opencode: .agents/skills/ygg-router/SKILL.md
  claude: .claude/skills/ygg-router/SKILL.md
---
# ygg-router

## When To Use

当用户消息提交时，`beforeSubmitPrompt` 根钩子已把检测结果落盘到
`yggforge-runtime/cache/last_trigger.json`。本技能负责读取该文件并按
`action` 路由到对应 ygg 功能（记/想/思/运维）。

## Steps

1. Read `yggforge-runtime/cache/last_trigger.json`（或部署后等价路径）。
2. 按 `action` 路由：
   - `skip` / 读不到 → 跳过 ygg 检索（fail open），仍执行综合回答策略。
   - `explicit_ygg` → 按「ygg + 自然语言」解释规则路由。
   - `remember` / `ingest` / `distill` / `recall` / `associate` / `tag` / `graph` /
     `dream` / `promote` / `status` / `deploy` / `sync` / `behavior` → 调对应 ygg 命令。
   - `default_on` → 模型先形成初步判断 → 提炼 seed tags → `ygg associate --tag ... --json`
     → Read 命中真源 → 必要时 `ygg recall` → 联网搜索 → 综合三源作答。
3. 综合回答：ygg 检索 + 模型推理 + 联网搜索；标注来源与置信度。

## Inputs

- `last_trigger.json`（由根钩子每条消息自动刷新）

## Outputs

- 路由后的 ygg 命令执行结果
- 综合三源的回答

## Notes

- 是否真正执行 ygg 命令由各命令 `behavior` 门禁（ask/allow/deny）决定；本技能只负责路由建议。
- 真源：`knowledge/rules/default-trigger-routing.md`、`knowledge/rules/standing-preference.md`。
- 详见 `docs/reference/triggers.md`。
