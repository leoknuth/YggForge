---
id: 20260701165030-kr$$$$-mapw$$$$-ktcc
title: Memory And Promotion Workflow
type: rule
status: active
confidence: high
source: agent-profile
scope: How user corrections become reusable knowledge
last_reviewed: 2026-07-01
owners:
  - team
tags:
  - memory
  - lessons
  - promotion
  - workflow
keywords:
  - remember
  - recall
  - dream
  - promote
  - 错题本
related:
  - 20260701165030-kr$$$$-gwfaa$$$-rjdq
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及用户纠错沉淀、运行时记忆、lesson 草稿、规则晋升时优先加载
---
# Memory And Promotion Workflow

## 何时应记录为经验

当出现以下任一情况时，应考虑把内容沉淀到 `knowledge/lessons/` 或 `knowledge/sources/distilled/`：

- 用户对 Agent 做了原则性纠正
- 用户明确要求“记住”“以后一直这样”“写进错题本/规则/规范”
- 一条偏好明显需要跨项目、跨会话复用

## 经验条目建议字段

字段权威见 `schemas/knowledge-item.schema.yaml`（v2，`type: lesson`）。

- 正文：`## Observation`（场景 / 问题）、`## Principle`（纠正后的原则）
- YAML：`applies_to` / `does_not_apply_to`（适用范围）、`promoted_to` / `reason_to_promote`（是否已晋升及原因）、`when_to_read`、`tags`

## 晋升条件

满足以下条件时，经验可考虑晋升为 `rules/` 或 `templates/`：

- 重复出现至少两到三次
- 适用边界清晰
- 不是工具偶然性
- 晋升后能降低未来歧义或返工

### 客观知识快速晋升（lessons）

对于**纯客观知识/信息**类草稿（参数表、事实记录、手册条目等，非主观偏好、非待验证纠错），可走自动晋升路径，无需等重复 2-3 次：

1. LLM 判断草稿为纯客观知识（调用时带 `--objective` 留痕）
2. 脚本自动跑标签联想查重（`ygg associate` hop=0）：无雷同 → 自动晋升
3. 有雷同 → 跳过为 `duplicate_candidate`，仍需人工审核

```text
ygg promote reference --entry <draft> --auto --objective
```

门禁：`promote.auto_to_reference`（默认 `allow`）。客观知识晋升到 `reference/`（非 `lessons/`）。

### 站立偏好快速晋升（rules）

当用户**明确表达站立偏好**时（「以后一直这样」「写成规则」「升级成规则」等），该话术本身即视为对强规范的人类确认，可自动晋升到 `rules/`，无需再等重复 2–3 次：

```text
ygg remember "……以后一直这样……" --as rule --tags ... --title ...
# 或正文/标题命中站立句式时自动等价于 --as rule
```

流程：`remember` 写入 inbox → 自动 `promote --auto --to rule --standing`。

门禁：

- `promote.auto_to_rule_on_standing`（默认 **allow**）— 仅站立偏好路径
- `promote.auto_to_rule`（默认 **deny**）— dream/批处理无显式站立意图时仍禁止静默写 rules

## 结构约束

- 稳定约束放 `rules/`
- 可复用操作流程放 `templates/` 或脚本
- 一次性纠错、反例、踩坑放 `lessons/`
- 不要把执行细节在多个规则里重复描述

## 当前最小自动化

当前仓库级自动化入口为：

- `ygg dream [--scan]`
  - 扫描运行时记忆层，找重复候选与待晋升候选
- `ygg remember <note>`
  - 先写入 `yggforge-runtime/memory/raw/`
  - 再镜像到 `knowledge/lessons/inbox/`
- `ygg recall <query>`
  - 检索运行时记忆层与 lesson 草稿
- `ygg promote <entry> reference|lesson|rule|template|decision`
  - 将 inbox 草稿晋升到对应目录
  - `--auto --to reference --objective`：客观知识 + 联想查重无雷同时自动晋升（`promote.auto_to_reference` 默认 allow）
  - `--auto --to rule --standing`：用户显式站立偏好自动晋升（`promote.auto_to_rule_on_standing` 默认 allow）
  - 批处理 `--auto --to rule`（无 `--standing`）仍受 `promote.auto_to_rule` 默认 deny 约束
- `ygg remember <note> [--as rule|--standing]`
  - 命中「以后一直这样 / 写成规则」等句式，或显式 `--as rule`，则写入 inbox 后自动走站立晋升
当前版本优先保证最小闭环，不自动维护所有索引文件。

## Applies To

- 经验沉淀
- 运行时记忆
- rule / template 晋升

## Not For

- 直接替代人工审核（rules 晋升仍必须人审；lessons 仅客观知识 + 无雷同时可自动）
