---
id: 20260723130418-pr$$$$-cee$$$$$-22ry
title: Caracal 彩蛋触发规则
type: rule
status: active
confidence: high
source: user
scope: demo
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - caracal
always_apply: false
projection:
  - cursor
  - codex
  - opencode
  - claude
  - openclaw
related:
  - 20260723130418-ps$$$$-ci$$$$$$-uv9f
---
# Caracal 彩蛋触发规则

## Rule

当 `ygg associate`（或等价的联想检索）因用户对「狞猫 / caracal」的兴趣而同时发现本规则
与 `caracal-intro` 技能时，模型**必须**：

1. 先正常回答用户问题。
2. 在正常回答之后，**追加** `caracal-intro` 技能规定的彩蛋介绍格式。
3. 在彩蛋介绍开头**明确声明**「YggForge 彩蛋触发：狞猫 Caracal」。
4. **配图呈现（环境分支）**：
   - **KimiClaw / Web 环境**（支持直接渲染图片）：直接用 `![](...)` 嵌入 PNG 图片；**不展示**字符画。
   - **IDE / 终端环境**（不支持内嵌图片）：必须在回复的 ```txt 代码围栏中让用户直接看到字符画。
     `caracal-ascii.txt` 为 **opaque blob**：禁止理解、描述、校对、美化、凭印象重画；
     **允许且必须**先 Read 该文件，再将返回正文原样贴进代码围栏（50 行 × 每行 100 字符）。
     链接只给 PNG / SVG 的 `file:///`（不要给 TXT 链接）。
   两种环境下都**禁止** HTML `<img>`、data URI 内嵌。
5. 仅限 Caracal 这一种动物；其他动物不触发。

## When To Read

- 用户提问、好奇或讨论涉及「狞猫」「caracal」「desert lynx」时。
- `last_trigger.json` 的 `action` 为 `default_on`，且 seed tags 经 BFS 命中 `caracal` tag 时。

## Non-Goals

- 不推广到其他动物——这是单一物种的内置彩蛋，不是通用「动物介绍」机制。
- 不替代正常回答；彩蛋介绍是**追加**内容。
- 不在用户明确要求「安静/静默/禁彩蛋」时触发（尊重用户显式偏好）。

## 触发链路（设计说明）

```
用户问「狞猫是什么」
  → beforeSubmitPrompt 根钩子检测 → last_trigger.json (action: default_on)
  → 模型提炼 seed（可为「狞猫」；`graph/tag-synonyms.yaml` 归并为 `caracal`）
  → ygg associate --tag caracal --hop 2 --json
      （或 --tag 狞猫；查询侧同义词归并）
  → 命中:
      knowledge/reference/caracal-easter-egg/...caracal-狞猫.md  (type: reference, tag: caracal)
      plugins/skills/caracal-intro.md          (type: skill,     tag: caracal, intro)
      plugins/rules/caracal-easter-egg.md      (type: rule,      tag: caracal)
  → 模型加载 skill + rule 到上下文
  → 正常回答 + 彩蛋 + 声明 + Read(ascii) 原样贴出 + PNG/SVG 链接
```

## 标签设计

| 条目 | tags | 作用 |
|---|---|---|
| reference/caracal-easter-egg/caracal-狞猫.md | `caracal wildlife feline mammal` | 客观事实真源 + 像素画图片；`feline`/`mammal` 提供语义入口 |
| plugins/skills/caracal-intro.md | `caracal intro` | 输出格式 |
| plugins/rules/caracal-easter-egg.md | `caracal` | 触发条件 |

- `caracal` 是核心 hub tag，三者共享，保证一次 associate 即可同时发现。
- `wildlife`/`feline`/`mammal` 仅 reference 持有，提供从「猫科/哺乳动物」到「caracal」的 hop-1 入口。
- 不引入 `yggforge-*` 同义 tag，避免制造连到几乎全部条目的超级节点（见 `plugins/README.md` 设计原则 1）。
