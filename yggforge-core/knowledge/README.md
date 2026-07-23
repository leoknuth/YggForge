# Knowledge

## 目录

- [1. 这一层是什么](#1-这一层是什么)
- [2. 先看哪一类](#2-先看哪一类)
- [3. 各子目录入口](#3-各子目录入口)

---

## 1. 这一层是什么

`knowledge/` 是 `YggForge` 的 canonical knowledge 层。

这里放的是：

- 稳定规则
- 可复用模板
- 经验与错题
- 设计决策
- 客观参考知识
- 外部来源材料

这里**不**放：

- Agent 私有全局目录
- 运行时记忆缓存（见 [../../yggforge-runtime/README.md](../../yggforge-runtime/README.md)）
- 联想图与机器索引（见 [../graph/README.md](../graph/README.md)）
- 可选人类 tag 导览导出（见 [../../yggforge-generated/README.md](../../yggforge-generated/README.md)）

## 2. 先看哪一类

| 你要找什么 | 入口 |
| --- | --- |
| 稳定规范 | [rules/README.md](rules/README.md) |
| 可复用模板 | [templates/README.md](templates/README.md) |
| 错题、踩坑、经验 | [lessons/README.md](lessons/README.md) |
| 客观参考知识（事实/基线/定义/对比） | [reference/README.md](reference/README.md) |
| 设计决策 | [decisions/README.md](decisions/README.md) |
| 外部来源与提炼材料 | [sources/README.md](sources/README.md) |
| tag 图与机器索引 | [../graph/README.md](../graph/README.md) |
| 可选人类 tag 导览 | [../../yggforge-generated/README.md](../../yggforge-generated/README.md) |

## 3. 各子目录入口

- [rules/README.md](rules/README.md)
- [templates/README.md](templates/README.md)
- [lessons/README.md](lessons/README.md)
- [reference/README.md](reference/README.md)
- [decisions/README.md](decisions/README.md)
- [sources/README.md](sources/README.md)
- [sources/inbox/README.md](sources/inbox/README.md)
- [sources/distilled/README.md](sources/distilled/README.md)

## 4. Front matter 与 Cursor 投影

条目使用**单文件** Markdown + YAML front matter（不拆 sidecar）。

原则：可枚举 / 结构化的元数据进 YAML；叙述性正文留在 Markdown。每条正式条目必须有 `type`：

| `type` | 目录习惯 | 正文侧重 |
| --- | --- | --- |
| `rule` | `rules/` | 规范叙述 |
| `lesson` | `lessons/` | Observation / Principle |
| `reference` | `reference/` | 客观描述（概述/参数/对比） |
| `decision` | `decisions/` | Context / Decision |
| `template` | `templates/` | 使用说明与骨架 |
| `source` | `sources/inbox/` 等 | 抽取长文 |
| `distilled-source` | `sources/distilled/` | 可选补充；facts 等在 YAML |

公共字段与 type 专有字段见：

- [../schemas/knowledge-item.schema.yaml](../schemas/knowledge-item.schema.yaml)（v2）
- 解析：`scripts/lib/front_matter.py`
- 校验：`scripts/knowledge/schema.py`（随 `ygg graph check` / `build` 扫描）
- 脚手架：[templates/README.md](templates/README.md)

需要 Cursor `alwaysApply` 的规则：真源保持 `.md`，在 front matter 设 `always_apply: true`，然后：

```powershell
.\ygg.ps1 project mdc
.\ygg.ps1 project mdc --check
```

生成/检查 `profiles/cursor/rules/**/*.mdc`。`projection_mode: sync` 由真源正文再生；`manual` 保留手写薄投影（如 `ygg-answer-synthesis.mdc`）。
