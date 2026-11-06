---
id: ygg-skill-yggforge
title: YggForge 触发路由技能
title_refined: yggforge skill
type: skill
status: active
confidence: high
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-24
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
  cursor: .cursor/skills/yggforge/SKILL.md
  codex: .agents/skills/yggforge/SKILL.md
  opencode: .agents/skills/yggforge/SKILL.md
  claude: .claude/skills/yggforge/SKILL.md
---
# yggforge

别名：`ygg`（Cursor 侧 `.cursor/skills/ygg/SKILL.md` 指向同一真源）。`/yggforge` 与 `/ygg` 等价触发本技能。

## When To Use

当用户消息提交时，`beforeSubmitPrompt` 根钩子按会话与消息身份原子保存检测结果。
本技能先验证结果属于本轮用户消息，再按 `action` 路由到对应 ygg 功能（记/想/思/运维）。
旧的全局 `cache/last_trigger.json` 不再作为可信输入。

## 显式调用语义（/yggforge 或 /ygg）

当用户通过 `/yggforge` 或 `/ygg` **显式调用**本技能时，视为**强制触发**：用户已明确要求执行 ygg 功能，不再依赖缓存结果的自动判定。

- 对受 `behavior` 门禁（ask/deny）且会修改状态的 ygg 命令（`remember` / `promote` / `deploy` / `sync` / `push` / `tag --add|--relate|--set-weight|--propagate` 等），附加 `--yes` 以 `force=allow` 直接执行，绕过 ask 询问与 deny 跳过——显式调用本身就是用户授权。
- 只读命令（`status` / `recall` / `associate` / `doctor` / `graph check` / `index --check`）无需 `--yes`。
- 安全边界：`--yes` 仅绕过 ask/deny 询问门禁；不改变命令本身的参数语义（不会把 `git push` 变成 force push，不会跳过显式指定的 `--dry-run`）。

## Steps

1. 按下节「触发结果验证」取得 `validation=matched` 的本轮结果。**显式 `/yggforge` 或 `/ygg` 调用时跳过此步**——直接按用户意图路由。
2. 按 `action` 路由：
   - `skip` / 读不到 → 跳过 ygg 检索（fail open），仍执行综合回答策略。
   - `explicit_ygg` → 按「ygg + 自然语言」解释规则路由。
   - `remember` / `ingest` / `distill` / `recall` / `associate` / `tag` / `graph` /
     `dream` / `promote` / `status` / `deploy` / `sync` / `behavior` → 调对应 ygg 命令。
   - `default_on` → 模型先形成初步判断 → 提炼 seed tags → `ygg associate --tag ... --json`
     → Read 命中真源 → 必要时 `ygg recall` → 联网搜索 → 综合三源作答。
3. 综合回答：ygg 检索 + 模型推理 + 联网搜索；标注来源与置信度。

## 触发结果验证

Cursor 的 `sessionStart` 协议提供本会话 ID。使用开发态或已部署核心包中
`profiles/cursor/hooks/ygg_pre_submit.py` 的绝对路径，以当前平台 Python 执行：

```text
<Python> <核心包绝对路径>/profiles/cursor/hooks/ygg_pre_submit.py --read-trigger --conversation-id <本会话ID> --prompt-from-env
```

将本轮完整用户原文安全传入 `YGG_TRIGGER_PROMPT`；宿主消息 ID 可得时再传 `--message-id`。
验证入口不依赖项目 cwd，会检查会话、消息/原文摘要和 5 分钟时效。
只有返回 `validation=matched` 才能使用 `action`；不要绕过验证直接读取缓存 JSON。

无 Cursor hook 或没有可核对的会话 ID 时，按本轮用户消息内化 `AGENTS.md` 触发规则，
或重新调用 `scripts/hooks/trigger_detector.py`，不沿用其它会话或上一轮缓存。
匹配失败、过期、缓存缺失时同样按本轮消息重新检测；不要求用户重复授权已经明确要求的操作。

## Inputs

- Cursor 钩子保存的本会话/消息触发结果（带 ID、原文摘要及 UTC 时间）
- 显式 `/yggforge` 或 `/ygg` 调用：用户自然语言意图

## Outputs

- 路由后的 ygg 命令执行结果
- 综合三源的回答

## Notes

- 自动触发时，是否真正执行 ygg 命令由各命令 `behavior` 门禁（ask/allow/deny）决定；**显式 `/yggforge` 或 `/ygg` 调用时按上文「显式调用语义」加 `--yes` 强制执行**。
- 真源：`knowledge/rules/default-trigger-routing.md`、`knowledge/rules/standing-preference.md`。
- 详见 `docs/reference/triggers.md`。
