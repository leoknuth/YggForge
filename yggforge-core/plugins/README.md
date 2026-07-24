---
id: ygg-plugins-readme
title: YggForge 内部插件
type: rule
status: active
confidence: high
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - yggforge
  - plugins
  - architecture
related:
  - ygg-skill-yggforge
  - ygg-mcp-gitlab
  - ygg-hook-pre-submit
---
# YggForge 内部插件（plugins/）

## 这是什么

`plugins/` 是 YggForge 的**可部署能力包**真源层，与 `knowledge/`（治理真源：lessons/templates/decisions/sources/rules）正交：

- `knowledge/` 回答「知道什么、约束什么、怎么晋升」——人审治理的知识资产。
- `plugins/` 回答「能调用什么能力、装到哪、依赖谁」——面向 Agent 的能力包。

两者复用同一 front matter schema（`schemas/knowledge-item.schema.yaml`）与 `KnowledgeEntry` 模型，由 `graph_scan` 一并索引。因此 `ygg associate` 的 tag BFS 联想能**同时**发现规则、经验、技能、MCP、钩子——这就是 YggForge 作为「智能插件管理器」的核心机制。

## 目录

| 子目录 | type | 投影目标（`ygg deploy` link/copy 薄入口） |
|---|---|---|
| `skills/` | `skill` | Cursor `.cursor/skills/`、Codex/OpenCode `.agents/skills/`、Claude `.claude/skills/` |
| `mcp-servers/` | `mcp-server` | Cursor `.cursor/mcp.json`、Codex `config.toml [mcp_servers]`、Claude `.mcp.json` |
| `hooks/` | `hook` | Cursor `~/.cursor/hooks.json`（根钩子一次性安装）、其余按 `trigger_tags` 联想触发 |
| `rules/` | `rule` | 规则包（机制规则与可投影规则切片；投影到 `.cursor/rules/*.mdc` 等） |

> **投影范围说明（P1-3）**：上表「投影目标」列出的是**规划中的各 Agent 原生落点**。当前 `ygg deploy` 仅对 **Cursor** 完成了 `profiles/cursor/` 薄入口的 link/copy 落地（rules / skills / hooks）。**Codex / OpenCode / Claude 等非 Cursor Agent 的 `profiles/<agent>/` 薄入口尚未建立**——这些 Agent 暂时通过整包投影 `yggforge-core` + 根 `AGENTS.md` 接入，原生 skill/mcp/hook 薄入口为后续工作。`project_to` 字段保留为规划声明，deploy 不据此自动生成。

## 设计原则

1. **不引入同义 tag**：`type` 字段已编码类别（skill/mcp-server/hook）。tag 只承载语义（git/mcp/trigger/cpp）。给每条都打 `yggforge-rules` 之类的同义 tag 会制造连到几乎全部条目的超级节点，破坏 BFS 选择性——明确拒绝。
2. **不追求与各 Agent 原生插件格式一一对应**：内部格式只被 YggForge 自己识别。对外投影时，`ygg deploy` 当前整包投影 `yggforge-core` 并叠加薄入口（如 Cursor `rules/*.mdc`、hooks）；**`project_to` 字段是规划中的原生投影目标声明，尚未由 deploy 自动生成各 Agent 原生 `SKILL.md` / 插件包**——发现靠 tag 联想，安装仍靠整包 + 手工/薄入口。
3. **不与外部 Agent 自身体系冲突**：YggForge 自成一套内部系统；无论外部用哪个 Agent，通过 YggForge 智能调用的内部功能保持一致格式与用法。
4. **联想发现 ≠ 安装依赖**：tag BFS 回答「想到什么」（associate）；插件依赖顺序用 `depends_on` 字段（显式 DAG）。两套机制共存，不互相替代。
5. **安装时只装一个根钩子**：`beforeSubmitPrompt` 根钩子是 bootstrap；之后 YggForge 内部自成体系，更稳定。

## 字段

复用 `common` 字段（id/title/status/tags/agent_targets/scope/confidence/last_reviewed/...）+ 各 type 专有字段（见 schema）。关键专有字段：

- `agent_targets`：投影目标 Agent 列表（cursor/codex/opencode/claude/openclaw）。
- `depends_on`：插件依赖（skill/mcp/rule id 列表），决定安装顺序。
- `project_to`：规划中的各 Agent 原生投影目标声明（**deploy 尚未按此字段生成原生 skill/插件**；当前以整包 `yggforge-core` + 薄入口为准）。
- `trigger_tags`（hook）：联想触发该钩子的 seed tag。

## 相关文档

- [../knowledge/rules/README.md](../knowledge/rules/README.md)（治理真源层）
- [../schemas/knowledge-item.schema.yaml](../schemas/knowledge-item.schema.yaml)（front matter schema）
- [../../docs/concepts/memory-and-association.md](../../docs/concepts/memory-and-association.md)（联想检索）
- [../../docs/concepts/layout.md](../../docs/concepts/layout.md)（目录边界）

## 内置彩蛋：Caracal 狞猫

`plugins/` 内置了一个跨层彩蛋，用于验证 `ygg associate` 能否从自然语言意图经 tag BFS
发现跨 `knowledge/` 与 `plugins/` 的关联条目：

- 客观知识真源：`knowledge/reference/caracal-easter-egg/20260723-130418-caracal-狞猫.md`（`type: reference`，含像素画图片）
- 介绍技能：`plugins/skills/caracal-intro.md`（`type: skill`，规定输出格式）
- 触发规则：`plugins/rules/caracal-easter-egg.md`（`type: rule`，定义触发条件）

三者共享 `caracal` tag。当用户问及狞猫时，模型除正常回答外，会追加规定格式的彩蛋介绍并明确声明触发。这是内置测试，也是 YggForge 联想记忆能力的端到端示范。

## 内置流程：三庭合议（ICJ）

多模型疑难任务编排——**初庭独立 → 议庭互评 → 裁庭（基座）终裁**；默认强制联网。

- 技能真源：`plugins/skills/tri-chamber-deliberation.md`（`type: skill`）
- 规则真源：`plugins/rules/tri-chamber-deliberation.md`（`type: rule`）
- Cursor 薄入口（投影源）：`profiles/cursor/skills/tri-chamber-deliberation/SKILL.md`  
  （由 `ygg deploy` link/copy 到 `~/.cursor/skills/` 或项目 `.cursor/skills/`；**不**在部署时现场生成）

共享 tag：`deliberation`（`icj` / `三庭合议` 等为其同义词，见 `graph/tag-synonyms.yaml`，查询时自动归并到 `deliberation`）。调用示例：

```text
三庭合议 kimi, GLM, Composer, Grok：<问题>
```
