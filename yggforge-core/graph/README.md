# Knowledge Graph

## 目录

- [1. 作用](#1-作用)
- [2. 文件分工](#2-文件分工)
- [3. TSV 是什么、和 CSV 有何不同](#3-tsv-是什么和-csv-有何不同)
- [4. 各 TSV 列含义](#4-各-tsv-列含义)
- [5. 有序分片与查询策略](#5-有序分片与查询策略)
- [6. 常用命令](#6-常用命令)
- [7. Agent 使用约定](#7-agent-使用约定)
- [8. 状态与新鲜度](#8-状态与新鲜度)

---

## 1. 作用

本目录是 YggForge 的**图索引真源**，随核心包部署，使 `ygg associate` 在部署后仍可命中：

- `tag-graph.yaml`：可编辑的 tag 邻接权威（人审）。
- `tag-synonyms.yaml`：同义词归并与 tag 规范语言（与邻接图同层）。
- `catalog/` + `tag-inverted/`：机器生成索引（由 `ygg graph build` 重建，入库）。

真源条目仍在 `../knowledge/` 与 `../plugins/`。可选人类 by-tag 导览与 PPMI 建议边在 `../../yggforge-generated/indexes/`（不入库、不部署）。三层边界见 [../../docs/concepts/layout.md](../../docs/concepts/layout.md)。

> 为什么机器索引也放在核心包内？因为它**随核心包部署**——部署到 `~/.cursor/yggforge-core/` 后，`associate` 直接读这里的 catalog 即可命中，无需另部署 `yggforge-generated/`。`yggforge-generated/` 只留 rendered/imports/manifests/indexes 建议边/scratch 等本机可再生产物。

## 2. 文件分工

| 文件 / 目录 | 权威性 | 位置 |
| --- | --- | --- |
| tag-graph.yaml | 可修改 | **本目录**（tag 邻接） |
| tag-synonyms.yaml | 可修改 | **本目录**（同义词 / 规范语言） |
| catalog/ | 生成 | **本目录**（`yggforge-core/graph/catalog/`） |
| tag-inverted/ | 生成 | **本目录**（`yggforge-core/graph/tag-inverted/`） |
| */manifest.json | 生成 | 同上 |

## 3. TSV 是什么、和 CSV 有何不同

- **TSV** = Tab-Separated Values（用 **Tab 制表符** `\t` 分隔列）
- **CSV** = Comma-Separated Values（用 **逗号** `,` 分隔列）

二者都是「一行一条记录、多列用分隔符切开」的纯文本表。本仓库选 TSV，是因为路径、标题里常出现逗号，用 Tab 分隔更少需要引号转义；对「按行排序 + 二分查找」也更干净。

注意：本实现里 **第一列是排序主键 key**，其余列是 payload；列表字段（多 tag / 多 id）在单元格内再用 `|` 连接，而不是再拆成更多 Tab 列。

## 4. 各 TSV 列含义

### 4.1 `catalog/*.tsv`（id → 条目信息）

按 **条目 id** 字典序排序。列（Tab 分隔）：

| 列序 | 字段 | 含义 |
| --- | --- | --- |
| 1 | `id` | 条目全局唯一 id（排序主键）；格式见 [../../docs/concepts/retrieval-conventions.md](../../docs/concepts/retrieval-conventions.md)「条目 id 约定」 |
| 2 | `path` | 相对核心包根的路径，如 `knowledge/rules/git-workflow.md` |
| 3 | `kind` | **列名历史遗留**：值为 front matter 的 **`type`**（`rule` / `lesson` / `decision` / `template` / `source` / `distilled-source`）。条目 YAML 请写 `type:`，不要写 `kind:` |
| 4 | `title` | 标题 |
| 5 | `tags` | 该条目的 tag 列表，多个用 `\|` 连接 |
| 6 | `related` | 直接关联的其他条目 id，多个用 `\|` 连接；可为空 |
| 7 | `priority` | 优先级：`high` / `medium` / `low` / `unset` |
| 8 | `status` | 当前生命周期状态 |
| 9 | `confidence` | 条目置信度 |
| 10 | `last_reviewed` | 最后审核日期 |
| 11 | `source_fingerprint` | 源文档 SHA-256，核验正文与索引一致性 |

示例（`<TAB>` = 制表符；id 里 `$` 为定长补位，见 retrieval-conventions）：

```text
20260701165030-kr$$$$-mapw$$$$-ktcc<TAB>knowledge/rules/memory-promotion.md<TAB>rule<TAB>Memory And Promotion...<TAB>memory|promotion|git<TAB>20260701165030-kr$$$$-gwfaa$$$-rjdq<TAB>high
```

### 4.2 `tag-inverted/*.tsv`（tag → 条目 id 列表）

> **什么是「反查表 / 倒排索引」？** 条目 front matter 的 `tags:` 字段是**正向**（条目→标签）；本表把它反过来，按 tag 列出所有命中条目的 id（标签→条目），所以叫「反查表」（信息检索里叫 inverted index / 倒排索引）。联想时给一个 tag，就能一步查出哪些条目带它。

按 **tag** 字典序排序。列：

| 列序 | 字段 | 含义 |
| --- | --- | --- |
| 1 | `tag` | 标签名（小写规范化，排序主键） |
| 2 | `ids` | 带该 tag 的全部条目 id，多个用 `\|` 连接（id 已排序） |

示例：

```text
agent<TAB>20260701231701-kr$$$$-acd$$$$$-e3p8|20260701165030-kr$$$$-gwfaa$$$-rjdq
git<TAB>20260701165030-kr$$$$-gwfaa$$$-rjdq|20260701165030-kr$$$$-mapw$$$$-ktcc
memory<TAB>20260701165030-kr$$$$-mapw$$$$-ktcc
```

### 4.3 `manifest.json`

描述该目录下有哪些分片文件、总行数/字节数、阈值配置；**不是**业务表数据。

## 5. 有序分片与查询策略

- 行格式见上一节；按 key **字典序**排序，便于行二分。
- 总大小低于 `full_load_max_bytes`（默认 1GiB）时全量载入内存。
- 单片超过 `shard_max_bytes` / `shard_max_lines` 时，按 key **前缀**裂变（非哈希）：先 1 字符 → 仍过大再加深到 `max_prefix_len`（默认 8）。
- 阈值见 `config/graph.defaults.json` 的 `storage.*`。
- **catalog** 的 key 是条目 id（时间在前），裂变按年/月/日自然散开；**tag-inverted** 的 key 是 tag 名，按字母前缀散开。

### 5.1 小索引（未裂变）

整表一个文件，前缀为空 → 文件名 `_all.tsv`：

```text
yggforge-core/graph/tag-inverted/
  _all.tsv          # 全部 tag 行，已按 tag 字典序排好
  manifest.json     # files: [{ "file": "_all.tsv", "prefix": "", ... }]
```

`_all.tsv` 内容示意：

```text
agent<TAB>idA|idB
cpp<TAB>idC
git<TAB>idB|idD
memory<TAB>idD
```

### 5.2 裂变后（超阈值）

**tag-inverted** 按 tag 首字符：

```text
yggforge-core/graph/tag-inverted/
  a.tsv             # agent…
  c.tsv             # cpp…
  g.tsv             # git…
  m.tsv             # memory…
  manifest.json
```

**catalog** 按 id 时间前缀（示意）：

```text
yggforge-core/graph/catalog/
  2026.tsv          # 当年全部；仍过大则加深
  202607.tsv        # 按月
  202608.tsv
  manifest.json
```

`manifest.json` 片段示意：

```json
{
  "format": "tsv-sorted-shards-v1",
  "key_order": "lexicographic",
  "shard_max_bytes": 8388608,
  "shard_max_lines": 100000,
  "files": [
    { "file": "a.tsv", "prefix": "a", "first_key": "agent", "last_key": "agent" },
    { "file": "g.tsv", "prefix": "g", "first_key": "git", "last_key": "git" }
  ]
}
```

查 `git`：manifest 选中 `g.tsv` → 该文件内二分到 `git` 行 → 得到 `id|id|…` → 再拿 id 去 catalog 解析路径。

## 6. 常用命令

```bash
ygg graph build
ygg graph check
ygg associate --tag simu --hop 2
ygg associate --tag git --tag workflow --json
```

`ygg graph build` **默认不**导出 `indexes/by-tag/`。需要人类导览时再执行 `ygg index` 或 `ygg graph build --with-by-tag`。

## 7. Agent 使用约定

面对用户问题 / 任务时，须按[综合回答策略](../../docs/reference/triggers.md#综合回答策略三源综合)综合三源（真源 `knowledge/rules/standing-preference.md`）：

1. **模型推理** — 先形成初步理解；
2. **ygg 联想检索** — 先 `ygg tag --language` 查 tag 规范语言（默认 `en`），再从对话提炼该语言的 seed tags，**优先对齐已有 tag 体系**（已有以英文为主就用英文，如 `simu`/`git`/`cpp`；无对应英文 tag 的中文概念中英双发，如 `--tag latte --tag 拿铁`），调用 `ygg associate --tag ...`（可用 `--hop`，查询侧自动经 `tag-synonyms.yaml` 归并），必要时 `recall`；按返回 `path` 阅读命中真源；
3. **联网搜索** — WebSearch / WebFetch；事实类、时效敏感类问题必须搜索；
4. **综合作答** — 把三源结果一并纳入回答，标注来源与置信度；不得仅凭 ygg 命中作答。

ygg 图索引是可审计的结构化联想层，不替代模型推理与联网验证。

## 8. 状态与新鲜度

- associate 默认最多返回 10 条；撤销、草稿与未生效规则退出默认检索。需要历史条目时显式使用 --include-inactive。
- graph check 是只读检查，不写分片。结果区分 consistent、migration_required、stale；旧格式只能核验已有元数据，不能宣称正文已核验。
- manifest 的 source_digest 与每条 source_fingerprint 用于核对源文档；associate 的陈旧标记只覆盖本次涉及条目，完整检查使用 graph check。
- graph build 才生成新索引。升级旧格式前保存备份、检查已有记录一致性，再在隔离副本验证新格式。
- 大索引分片在单次进程内使用有界缓存；这不等于磁盘上的逐行随机访问，也不构成大规模性能评测。

源文档指纹采用 UTF-8 文本并将 CRLF 归一为 LF，与 Git 检出规范一致；规范化只用于指纹计算，不改写原始正文。
