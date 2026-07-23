---
id: 20260722221035-kr$$$$-$$$$$$$$-46c7
title: 问题解决：首次失败后优先联网检索
title_refined: 一次失败后应联网搜索方案
type: rule
status: active
confidence: high
source: user
scope: cross-project
recorded_at: 2026-07-22
last_reviewed: 2026-07-22
owners:
  - user
tags:
  - agent
  - workflow
  - troubleshooting
  - web-search
  - discipline
keywords:
  - web search
  - fail once
  - don't thrash
related: []
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 排障、修 hook/部署/环境差异、依赖报错、协议字段不明等「卡死」场景
  - 准备连续改同一处代码/配置做第二次尝试之前
promoted_to: rule
---
# 问题解决：首次失败后优先联网检索

## Rule

- 对同一问题，本地推理或改动**尝试 1 次仍未解决**时，必须先联网检索（官方文档、Issue、论坛、发布说明），再继续改。
- 禁止在没有新外部信息的情况下，对同一根因假设反复试错。
- 检索应带着具体报错/字段名/平台（如 Windows GBK、Cursor hooks stdin）去搜，而不是泛泛「怎么修」。

## Applies To

- 所有 Agent 排障与实现任务（跨项目）
- 尤其是第三方工具协议、OS/locale、编码、CI 环境差异类问题

## Not For

- 用户已给出明确可执行步骤、只需照做的任务
- 纯仓库内真源已覆盖、且首轮已命中正确条目的问题
- 明确的离线/禁网场景（用户声明「这次不要联网」时除外）

## Rationale

- 编码/钩子/平台类问题往往是上游已知 bug；闷头改脚本成本高、还容易引入无效复杂度。
- 「一次失败 → 先搜」比「搜完再动手」更平衡：保留本地首轮判断，又避免无效循环。
