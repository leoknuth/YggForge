---
id: ygg-rule-tri-chamber
title: 三庭合议（ICJ）触发与不变量
title_refined: "tri-chamber-deliberation rule"
type: rule
status: active
confidence: high
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - deliberation
  - agent
  - workflow
always_apply: false
projection:
  - cursor
  - codex
  - opencode
  - claude
  - openclaw
related:
  - ygg-skill-tri-chamber
---
# 三庭合议触发规则

## Rule

当用户意图匹配「三庭合议 / ICJ / 合议三轮 / model council」等（见下），或
`ygg associate` 因 seed tags 命中 `deliberation` / `icj` 而同时发现本规则与
`tri-chamber-deliberation` 技能时，**当前基座 Agent 必须**：

1. 加载并严格遵守 `plugins/skills/tri-chamber-deliberation.md` 的三轮协议。
2. 解析 **问题** 与 **模型列表**；缺一则先澄清再开跑。
3. **默认强制联网**（官方文档、官网、权威百科、权威书籍/教材、相关标准与论文等）；
   仅当用户明确禁网时关闭，并在裁定书标注离线。
4. 按 **初庭 → 议庭 → 裁庭** 顺序执行；不得跳轮。
5. 初庭/议庭在隔离 worktree（或平台等价物）中进行；**只有裁庭**可改主工作树（且仅当用户要求落地）。
6. 终裁输出「三庭合议 · 裁庭裁定」结构；落地则附验收结果。

## When To Read

触发词（中英、大小写不敏感），例如：

| 模式 | 示例 |
|---|---|
| 三庭合议 | `三庭合议 kimi, Grok：……` |
| ICJ / Independent-Critique-Judge | `ICJ with Composer, GLM — …` |
| 合议三轮 | `合议三轮：先各自再互评最后你拍板` |
| model council / debate council | `model council: …` |
| 显式流程描述 | `先让各模型独立答，再互相评议，最后你汇总` |

亦可通过联想：`ygg associate --tag deliberation` / `--tag icj`。

## Non-Goals

- 不替代简单问答或单模型快速修复——用户未请求合议时不要强行开三庭。
- 不把 `/best-of-n` 单独跑完就当作三庭合议完成（缺议庭与裁庭不算）。
- 不在无可用模型 slug 时编造模型身份。
- 不在用户要求「安静/跳过合议」时坚持开跑。

## 不变量

1. **独立先于交流**：议庭开始前，初庭答案不得互相可见。  
2. **交流必须点名**：议庭须点名评议其他模型，并产出共识/分歧表。  
3. **共识≠验证**：裁庭不得仅以多数票定案；须论证，并在事实点上可核对来源。  
4. **单一裁庭**：终裁权在基座（或用户显式指定的 moderator）；候选不得越权落地。  
5. **联网默认开**：关闭须用户显式声明。

## 触发链路（设计说明）

```
用户：三庭合议 A, B, C：<问题>
  → 基座加载本规则 + tri-chamber-deliberation 技能
  → Round 0 联网简报 + ygg associate（可选）
  → Round 1 并行隔离初庭（best-of-n-runner / worktree）
  → Round 2 resume 交叉评议
  → Round 3 基座裁庭裁定（±主仓落地）
```

## 标签设计

| 条目 | tags | 作用 |
|---|---|---|
| plugins/skills/tri-chamber-deliberation.md | `deliberation icj agent workflow` | 编排协议 |
| plugins/rules/tri-chamber-deliberation.md | `deliberation icj agent workflow` | 触发与不变量 |

- `deliberation` 为 hub；`icj` 为短别名（经 synonyms 可归并）。
- 不引入 `yggforge-*` 万能 tag。
