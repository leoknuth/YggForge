---
id: 20260701165030-kl$$$$-ap$$$$$$-qzv9
title: 从 agent-profile 吸收的经验
type: lesson
status: active
confidence: medium
source: agent-profile
scope: cross-project
recorded_at: 2026-07-01
last_reviewed: 2026-07-22
tags:
  - migration
  - lessons
  - memory
keywords:
  - agent-profile
  - migration
  - rules
  - templates
related:
  - 20260701165030-kr$$$$-mapw$$$$-ktcc
priority: medium
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及从旧知识系统迁移到 YggForge、判断哪些经验该晋升时优先加载
applies_to:
  - 知识体系迁移
  - 经验抽取
  - 规则晋升判断
does_not_apply_to:
  - 具体部署命令说明
---
# 从 agent-profile 吸收的经验

## 背景

本条目记录从参考仓库 `agent-profile` 中吸收出来的、对 `YggForge` 有长期价值的经验。

## 经验 1：规则不要直接堆成扁平文件墙

- 现象：当规则、技能、补丁规则越来越多时，扁平目录很快出现检索困难和重复表达。
- 结论：知识真源应按“规则 / 模板 / 经验 / 决策 / 来源”分层，而不是只按工具目录组织。
- 迁移结果：`YggForge` 采用 `knowledge/` 分层，`profiles/` 只负责投影。

## 经验 2：错题本机制非常有价值

- 现象：很多高价值纠正并不是正式规则，但值得跨会话保留。
- 结论：应建立从“纠错记录”到“规则/模板晋升”的明确通道。
- 迁移结果：增加 `memory-promotion.md`，并把错题本视为 `lessons/` 的重要来源。

## 经验 3：执行步骤必须有单一事实源

- 现象：当规则文件和技能文件同时描述同一执行流程时，很容易出现冲突、冗余和漂移。
- 结论：触发条件放规则，步骤细节收敛到单一流程说明或脚本入口。
- 迁移结果：`YggForge` 把通用原则放 `rules/`，把工具/部署流程放 `scripts/` 和部署文档。

## 经验 4：路径表达必须区分交互与落盘

- 现象：聊天里不展开路径容易歧义，文档里写死绝对路径又会破坏可移植性。
- 结论：交互时可展开绝对路径，持久化文档默认保持相对或 `~` 风格。
- 迁移结果：新增 `path-expression.md`。

## 经验 5：Git 状态结论必须以命令结果为准

- 现象：对“无差异”“已推送”的口头推断很容易出错。
- 结论：git 相关结论必须由实际命令支持，并保持步骤串行。
- 迁移结果：新增 `git-workflow.md`。

## 经验 6：注释应服务当前仓库，而不是记录外部血统

- 现象：在代码注释中写“从某项目拷贝”会污染当前仓库语义边界。
- 结论：外部来源应进入设计文档、提交信息或来源条目，而不是代码注释。
- 迁移结果：新增 `comment-boundaries.md`。
