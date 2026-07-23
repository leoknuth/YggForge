---
name: ygg-router
description: >-
  YggForge 触发路由：读取 last_trigger.json，按 action 路由 remember/associate/deploy 等。
  在处理带 ygg 强制钩子的会话、或需要按 last_trigger 路由时使用。
  真源在 yggforge-core/plugins/skills/ygg-router.md。
---
# ygg-router（Cursor 薄入口）

本文件是 **profiles 投影层** stub。路由细则不在这里。

1. Read 并遵循：
   - `yggforge-core/plugins/skills/ygg-router.md`（开发态）
   - 或 `~/.cursor/yggforge-core/plugins/skills/ygg-router.md`（已部署）
2. 先 Read `yggforge-runtime/cache/last_trigger.json`（或部署约定等价路径），再按 `action` 执行。
