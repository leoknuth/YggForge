# 04 · 待办项实现细则

> 对话层摘要：[03-optimizations.md](03-optimizations.md)。权重数学：[05-weight-design.md](05-weight-design.md)。  
> 行为闸门 / channel 用法见 [../reference/behavior-config.md](../reference/behavior-config.md)（非本目录待办）。

## O1 · weight → expand

**语义：** `weight∈[0,1]` 越高越强；省略默认建议 **0.70**。

**算法：**

```text
edge cost = -ln(max(w, ε))     # ε≈1e-9
path strength = ∏ w_i
path cost = Σ cost_i
expand skip if w < min_expand  # 默认 0.15
排序键: (hop ASC, path_cost ASC)
```

**落点：**

- `knowledge/graph.py`：`TagGraph.expand` 使用 weight；加载时建议对称化 `max(w_ab,w_ba)`
- `config/graph.defaults.json`：`weight.min_expand`、`weight.default`
- `cmds/graph/associate.py`：JSON 增 `strength`、`path`
- 写入：`ygg tag --set-weight` → `core_write.operations.tag_weight_update`

**验收：** 同 hop 下高 weight 邻居靠前；`w=0.1` 边不出现在 expand。

**禁止：** 按 hit_count 静默改 `tag-graph.yaml`。

---

## O2 · PPMI 建议

**统计：** 条目级 tag 共现；PPMI = max(0, log p(i,j)/(p(i)p(j)))。

**输出：** `yggforge-generated/indexes/tag-suggestions.json`

**CLI：** `ygg tag --suggest`；`--apply` → `authorize("core_write.operations.tag_suggest_apply")`。

**规则：** 建议 weight 封顶 **0.65**；已存在权威边默认不覆盖；`support` 低于阈值丢弃。

**验收：** dry-run 列出边；apply 后 yaml 有边且 Git diff 可审。

---

## O3 · 根骨架

**目标连通（示例）：**  
`agent` ↔ `workflow` ↔ `memory` ↔ `git`；`cpp` ↔ `hpc` / `performance`。

**做法：** 编辑 `graph/tag-graph.yaml` + `graph/tag-synonyms.yaml`；边权 0.55–0.85。

**验收：** 从任一工程根 `associate --tag X --hops 2` 能碰到至少另一根域。

---

## O5 · 时间窗

**CLI：** `--after` / `--before`（recall / dream）。

**锚点：** `updated` → `created` → `recorded_at` → mtime。

**验收：** `--after 2026-07-01` 过滤掉更早条目。

---

## O6 · 半衰期

**公式：** `score' = score * 0.5 ** (age_days / half_life_days)`

| kind | half_life | 衰减 |
| --- | ---: | --- |
| observation | 14d | 开 |
| lesson | 90d | 开 |
| rule / decision | — | **关** |

**验收：** 同关键词下新 observation 排在年前 observation 前；rule 不受 age 打压。

---

## O8 · 渐进加载

| 层 | 内容 |
| --- | --- |
| L0 | 标题 + 主 tags |
| L1 | 摘要 / 首 N 行 |
| L2 | 全文 |

**CLI：** `--progressive` · `--budget-tokens N`。

**验收：** 小预算不输出全文；加大后出现 L2。

---

## O9 · dream 管家

**增强报告块：**

1. 共现 Top-N（可复用 O2）  
2. 可选社区簇（feature；无 networkx 则跳过）  
3. 晋升理由模板 + 缺 evidence 否  
4. 孤岛 tag  

**硬约束：** 永不自动 `promote`。

---

## O10 · 语义 + RRF

**开关：** `behavior.features.semantic_retrieval`（默认 false）。

**融合：** RRF `score(d) = Σ 1/(k + rank_i(d))`，`k≈60`。  
通道：tag-associate、BM25/关键词、可选向量。无 embedding → 仅前两路。

---

## O11 · evidence

```yaml
evidence:
  - path: yggforge-runtime/memory/raw/...
    excerpt: "..."
    recorded_at: 2026-07-01
```

**promote：** 源 observation 写入 evidence；缺则 warn。  
**dream：** 候选标注 `missing_evidence`。

---

## O12 · 质量/归档

**输出：** `generated/.../archive-suggestions.json`（建议，不删）。  
**删除 core：** 必须 ask/deny。

---

## O13 · MCP

**Tools：** `ygg_associate` · `ygg_recall` · `ygg_remember` · `ygg_dream_status` · `ygg_behavior_get`  
写路径经 `policies/behavior.py` / `policies/core_write.py`。

---

## O14 · export

```text
ygg export --format obsidian|plain|graphrag-input --out <dir>
```

只读；不改 core。

---

## O15 · extract 对接

外部工具 → `knowledge/sources/inbox/`；合并 `prefer_existing`。

---

## O16 · TaskCanvas

**路径：** `yggforge-runtime/memory/canvas/<task-id>.md`  
默认不进 knowledge；结束可 dream 扫描是否 promote。

---

## 配置键速查

| 能力 | 配置 |
| --- | --- |
| 行为闸门 / features | `behavior.defaults.yaml` |
| 图权 / 扩跳 | `graph.defaults.json` |
| 记忆半衰期等 | `memory.defaults.json` |
| channel 词典 | `channels.yaml` |
| 本机覆盖 | `yggforge-runtime/config/*.local.*` |
