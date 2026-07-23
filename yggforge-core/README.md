# yggforge-core

本目录是 **可部署核心包**（`CORE_ROOT`）：进 git、可投影到各 Agent 的 `yggforge-core/`。

## 包含什么

| 目录 | 职责 |
| --- | --- |
| `knowledge/` | 知识真源（含 `knowledge/templates/` 条目模板） |
| `profiles/` | 各 Agent 投影入口 |
| `scripts/` | CLI 与自动化 |
| `config/` | 默认可提交配置（`*.defaults.json`） |
| `graph/tag-graph.yaml` | 可编辑的 tag 邻接权威 |
| `schemas/` | 元数据 schema |

## 不包含什么（刻意拆出）

| 目录 | 去向 |
| --- | --- |
| 可选 by-tag 导览 | `yggforge-generated/indexes/` |
| 运行时记忆 / 本机 `*.local.json` | `yggforge-runtime/` |
| 部署清单 / scratch | `yggforge-generated/` |

> 注：图机器索引（`catalog/` + `tag-inverted/`）位于本包 `graph/`，随核心包部署，使 `associate` 在部署后仍可命中。

完整三层说明与关系图见 [../docs/concepts/layout.md](../docs/concepts/layout.md)。

## 部署形态

- Cursor：`~/.cursor/yggforge-core` → 本目录
- Codex：`~/.codex/yggforge-core` → 本目录
- OpenCode：`~/.config/opencode/yggforge-core` → 本目录

配置见 `config/deploy.defaults.json` 中的 `core_bundle`。
