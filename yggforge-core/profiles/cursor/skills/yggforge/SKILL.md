---
name: yggforge
description: >-
  YggForge 触发路由：校验本会话与本轮消息的触发结果，按 action 路由 remember/associate/deploy 等。
  在处理带 ygg 强制钩子的会话、或需要按已验证的触发结果路由时使用。
  显式 /yggforge 或 /ygg 调用为强制触发，对写命令附加 --yes 绕过 behavior 门禁。
  真源在 yggforge-core/plugins/skills/yggforge.md。别名 ygg 指向同一真源。
---
# yggforge（Cursor 薄入口）

本文件是 **profiles 投影层** stub。路由细则不在这里。别名 `ygg`（`.cursor/skills/ygg/SKILL.md`）等价触发。

1. Read 并遵循：
   - `yggforge-core/plugins/skills/yggforge.md`（开发态）
   - 或 `~/.cursor/yggforge-core/plugins/skills/yggforge.md`（已部署）
2. 按真源「触发结果验证」调用核心包内绝对路径的 `ygg_pre_submit.py --read-trigger`，只有会话、消息/原文和时效匹配后才按 `action` 执行。无 hook / 无会话身份时按本轮消息内化 AGENTS.md 或重新检测，不读旧全局缓存。
3. 显式 `/yggforge` 或 `/ygg` 调用时为强制触发：跳过缓存判定，对受 behavior 门禁的写命令附加 `--yes` 直接执行（见真源「显式调用语义」）。
