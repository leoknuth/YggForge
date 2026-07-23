---
id: 20260722222018-kr$$$$-y$$$$$$$-ygux
title: 回答时综合 ygg 联想、模型思考与联网搜索
title_refined: 综合回答策略：ygg 联想 + 模型思考 + 联网搜索
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
  - web-search
  - model-reasoning
  - synthesis
promoted_to: rule
when_to_read:
  - 向用户回答任何问题时（纯运维指令与用户声明禁网/静默除外）
always_apply: true
projection_mode: manual
projection:
  - profiles/cursor/rules/ygg-answer-synthesis.mdc
---
# 回答时综合 ygg 联想、模型思考与联网搜索

## Rule

- 回答任何问题时，必须综合三个信息源：`ygg` 联想/检索结果、模型自身推理、联网搜索；不得仅凭 `ygg` 联想结果作答。
- 三者权重不由固定比例决定，而由 agent 根据问题性质、上下文、时效性与置信度自行判断：
  - 时效敏感或事实易变的问题 → 提高联网搜索权重；
  - 仓库内工程规范/历史决策类问题 → 提高 `ygg` 检索权重；
  - 推理/权衡/方案设计类问题 → 提高模型自身思考权重。
- 最终回答应标注各部分信息的来源与置信度，便于人类核验。
- Cursor 强制层：`profiles/cursor/rules/ygg-answer-synthesis.mdc`（`alwaysApply`）+ `ygg_session_protocol.py` 会话协议 + `docs/reference/triggers.md`「综合回答策略」节；不依赖 `associate` 碰巧命中本规则。

## Applies To

- 所有需要向用户回答问题的场景（`scope: cross-project`）
- 所有接入 YggForge 的 agent（cursor / codex / opencode 等）

## Not For

- 纯运维执行类指令（如 `ygg deploy`、`ygg sync`）
- 用户声明「静默模式」「不要联网」时跳过联网与 ygg
- 纯问候可仅用模型简短回应
