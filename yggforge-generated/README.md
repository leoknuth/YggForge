# yggforge-generated

**可再生产物层**（`GENERATED_ROOT`）。不是知识真源，也不随 Agent 整包部署。

## 放什么

| 子目录 | 内容 | 如何再生 |
| --- | --- | --- |
| `deploy-manifests/` | 最近一次 deploy 清单 | `ygg deploy` |
| `rendered/` | render 模式中间产物 | `ygg deploy … render` |
| `imports/` | copy/render 回流供人工复核 | `ygg import` |
| `indexes/by-tag/` | 可选人类 tag 导览页 | `ygg index` |
| `indexes/tag-suggestions.json` | PPMI 共现建议边 | `ygg tag --suggest` |
| `scratch/` | 临时草稿、`.tmp-*`、实验解压物 | 可删 |

## 不放什么

- 可审规范 / 模板 / 经验正文 → `yggforge-core/knowledge/`
- 图索引（tag 邻接权威 + 同义词 + 机器索引 catalog/tag-inverted）→ `yggforge-core/graph/`（随核心包部署，使 associate 部署后可命中）
- 本机记忆与 `*.local.json` → `yggforge-runtime/`

默认几乎全部被 git 忽略；只提交本 README 与本目录 `.gitignore`。
