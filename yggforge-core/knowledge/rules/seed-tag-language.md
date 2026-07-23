---
id: 20260722225400-kr$$$$-s$$$$$$$-tgln
title: 提炼 seed tag 时对齐已有体系并中英双发
title_refined: Seed Tag 语言对齐策略
type: rule
status: active
confidence: high
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-22
last_reviewed: 2026-07-22
tags:
  - answer-strategy
  - ygg
  - associate
related:
  - 20260722222018-kr$$$$-y$$$$$$$-ygux
promoted_to: rule
reason_to_promote: 不同模型 seed tag 语言偏好不一致导致检索命中率不稳，需统一为「对齐已有体系 + 中英双发 + synonyms 兜底」的确定性策略。
when_to_read:
  - 调用 ygg associate 或提炼 seed tags 之前
always_apply: false
---
# 提炼 seed tag 时对齐已有体系并中英双发

## Rule

- tag 规范语言由 `graph/tag-synonyms.yaml` 的 `language` 字段配置（`en`/`zh`，缺省 `en`）；生成 seed tags 或新增 tag 前先 `ygg tag --language` 查询当前语言限制，按返回值选择 tag 语言（默认 `en` → 用英文 tag）。
- 提炼 seed tag 时，**优先对齐知识库已有 tag 体系**，而非自行翻译：
  - 优先从命中条目的 `tags` 字段、或 `ygg tag --list` 复用已有 key；
  - 已有体系以英文为主时用英文；不确定时先 `ygg tag --list` 确认，避免每次盲猜。
- 遇到无对应英文 tag 的中文概念时，**中英双发**（如 `--tag latte --tag 拿铁`）：
  - 英文命中已有英文索引；
  - 中文为未来中文索引/正文检索留种，且经 `tag-synonyms.yaml` 归并到英文标准 tag。
- 不得「强行翻译成英文」了事——若翻译出的 key 不在索引里，照样命中不了；对齐的对象是「已有索引 key」，不是「英语」这个语言。
- 查询侧已对 `tag-synonyms.yaml` 归并：中文 seed tag 会自动映射到 canonical 英文 tag，配置见 `graph/tag-synonyms.yaml`。

背景：`ygg associate` 是 tag 精确匹配（`normalize_tag` 后查 `tag-inverted` + `tag-graph` BFS 扩展），不做中英文翻译。本仓库知识库的 tag 体系以英文为主；不同模型提炼语言偏好不同，叠加 Windows argv 对中文的编码损坏，会导致 `hit_count=0`。

## Applies To

- 所有调用 `ygg associate`（或内部 `KnowledgeGraphIndex.associate`）的场景
- 所有接入 YggForge 的 agent

## Not For

- 纯运维指令（`status` / `deploy` / `sync`）不涉及 seed tag
