# 知识条目模板

## 目录

- [1. 目的](#1-目的)
- [2. 覆盖范围](#2-覆盖范围)
- [3. 使用方法](#3-使用方法)
  - [新增规则](#新增规则)
  - [新增经验](#新增经验)
  - [新增决策](#新增决策)
  - [新增实现模板](#新增实现模板)
  - [新增来源提炼](#新增来源提炼)
- [4. frontmatter 约定](#4-frontmatter-约定)
- [5. 编写原则](#5-编写原则)

---

## 1. 目的

为了避免知识条目越写越散，`YggForge` 现在提供统一模板。

模板目录：

- `../../yggforge-core/knowledge/templates/`

## 2. 覆盖范围

当前提供：

- 规则模板
- 经验模板
- 决策模板
- 实现模板
- 来源提炼模板

## 3. 使用方法

### 新增规则

1. 从 `../../yggforge-core/knowledge/templates/rule.template.md` 复制
2. 放到 `knowledge/rules/`
3. 修改 frontmatter
4. 更新 `knowledge/rules/README.md`

### 新增经验

1. 从 `../../yggforge-core/knowledge/templates/lesson.template.md` 复制
2. 放到 `knowledge/lessons/`
3. 正文写 Observation / Principle；适用范围与晋升意图写进 YAML（`applies_to` / `promoted_to` 等）

### 新增决策

1. 从 `../../yggforge-core/knowledge/templates/decision.template.md` 复制
2. 放到 `knowledge/decisions/`
3. 用递增编号命名更好
4. 正文写 Context / Alternatives / Decision / Consequences；后果列表可进 YAML

### 新增实现模板

1. 从 `../../yggforge-core/knowledge/templates/implementation-template.template.md` 复制
2. 放到 `knowledge/templates/`

### 新增来源提炼

1. 从 `../../yggforge-core/knowledge/templates/distilled-source.template.md` 复制
2. 放到 `knowledge/sources/distilled/`

## 4. frontmatter 约定

权威字段表：`yggforge-core/schemas/knowledge-item.schema.yaml`（v2）。

索引必填：`id`、`title`、`status`、`type`。

公共推荐基线：`confidence`、`last_reviewed`、`owners`、`source`、`tags`、`scope`、`when_to_read`、`related`。

按 `type` 再填专有字段（如 lesson 的 `applies_to`，distilled-source 的 `facts`/`inferences`/`practices`/`risks`，rule 的 `always_apply`）。结构化列表进 YAML，不要在正文用 `## When To Read` 等重复。

## 5. 编写原则

- 规则写约束，不写长篇背景故事
- 经验写 Observation / Principle；适用边界进 YAML
- 决策写 Context / Alternatives / Decision；后果列表可进 YAML（`consequences_*`）
- 来源提炼用 YAML 区分事实与推论
- 模板要附适用边界和验证方式
