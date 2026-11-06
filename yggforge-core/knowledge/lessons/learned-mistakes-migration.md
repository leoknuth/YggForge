---
id: 20260714144840-kl$$$$-aplm$$$$-80a9
title: 从 agent-profile learned-mistakes 挑拣的稳定条目
type: lesson
status: active
confidence: medium
source: agent-profile
scope: cross-project
recorded_at: 2026-07-14
last_reviewed: 2026-07-22
tags:
  - migration
  - lessons
  - memory
keywords:
  - learned-mistakes
  - agent-profile
related:
  - 20260701165030-kr$$$$-mapw$$$$-ktcc
priority: medium
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 需要确认哪些历史纠错已晋升为 YggForge 规则、哪些仅作归档参考时
applies_to:
  - 从 agent-profile 迁出后的行为对齐
does_not_apply_to:
  - 继续运行 agent-profile 的 cursor_global_sync.py 闭环
---
# 从 agent-profile learned-mistakes 挑拣的稳定条目

## 已晋升为 knowledge/rules（不必再按旧路径执行）

| 原错题标题 | 现落点 |
| --- | --- |
| 代码注释统一为中文 / 默认不保留旧接口兼容层 | `compatibility-defaults.md` |
| 注释不引用其他仓库/项目 | `comment-boundaries.md` |
| 交互中“项目根”必须展开 / 文档不展开绝对路径 | `path-expression.md` |
| Markdown 文档头部必须有目录导引 | `markdown-docs.md` |
| C++ 指针引用 / pragma once / 注释模板 / 禁用 doxygen 尾随 | `cpp-style.md` |
| Git 依赖步骤禁止并行 / 回报以 show --stat 等 | `git-workflow.md` |
| 任意框架未明说则不设置 | — |
| 「永远记住」须触发错题本流程 | `memory-promotion.md` + `ygg remember` |

## 明确不再沿用（绑定旧 Cursor 回收闭环）

以下条目依赖 `~/.cursor` 自动回收 / `global-cursor-sync`，在 YggForge link 部署模型下**不再作为行为约束**：

- 修改 `~/.cursor` 后需同轮自动回收
- 回收后差异判定 / 自动 git push / 风险确认边界等 agent-profile 专属流程

记忆与晋升请改用：`ygg remember` → `knowledge/lessons/inbox/` → `ygg promote`。
