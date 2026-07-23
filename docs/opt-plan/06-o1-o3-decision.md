# O1–O3 落地裁定（2026-07-23）

> 综合 `/best-of-n`（Composer / kimi / GLM / Grok）设计稿，从第一性原理筛选后的**最终决定**。
> 规格原文：[03](03-optimizations.md) · [04](04-specs.md) · [05](05-weight-design.md)。

## 共识保留

| 参数 | 值 | 理由 |
| --- | ---: | --- |
| `weight.default_edge` | 0.70 | 省略 weight 时中强档；不默认 1.0 |
| `weight.min_expand` | 0.15 | 弱于噪声门槛不渗流 |
| `weight.epsilon` | 1e-6 | 防 ln(0) |
| `weight.hop_decay` | 0.75 | 条目级远跳轻罚 |
| `weight.undirected_load` | true | `max(w_ab,w_ba)` |
| `default_hop` | 2 | 联想宽度/噪声折中 |
| `suggest.min_cooccur` | 3 | 抑一次偶合（PPMI 稀有词偏置） |
| `suggest.w_cooccur_*` | 0.25–0.65 | 统计边永远低于人工默认 0.70 |
| `suggest.ppmi_tau` | 2.0 | tanh 映射落中强 |
| `suggest.apply_floor` | 0.55 | apply 后至少可扩 |
| `tag_suggest_apply` | ask | 批量回写必须人审 |

## 算法裁定（O1）

- **clean break**：`TagGraph.expand` 返回 `Dict[str, TagExpandInfo]`，不再返回 `{tag: hop}`。
- 路径强度 `∏w` ↔ 代价 `-ln(w)`；在 `hop≤H` 下用优先队列求最小代价（hop-constrained most-reliable path）。
- 排序：`(hop ASC, −strength DESC, …)`；JSON 暴露 `strength` / `path` / `path_cost`。

## 建议裁定（O2）

- CLI：`ygg tag --suggest` → `yggforge-generated/indexes/tag-suggestions.json`；`--apply` 走 `tag_suggest_apply`。
- PPMI + Laplace；denylist/`max_tag_frequency` 抑 hub；每 tag top-k。
- **不**静默按 hit_count 升权；**不**把共现边写成 1.0。

## 骨架裁定（O3）

并集四路缺口，补/校准：

- **跨域桥**：`ygg↔agent`、`cpp↔workflow`、`workflow↔performance`
- **主轴直连**：`cpp↔hpc`、`memory↔git`、`workflow↔memory`、`ygg↔workflow/memory`
- 根轴边权落在 **0.60–0.85**；演示域（coffee 等）可暂留 1.0

验收：`associate --tag ygg --hop 2` 触达 agent/workflow；`associate --tag cpp --hop 2` 触达 workflow/agent。

## 明确不做

- 兼容旧 `expanded_tags: {tag: hop}` 整数形态
- 自动 MST / 按频率静默改权威边
- 权威边时间衰减回写
