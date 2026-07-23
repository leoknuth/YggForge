# 优化计划（仅后续建议）

本目录**只收录尚未完成、建议继续做的优化**。  
已具备的能力（behavior 闸门、channel、core_write 委托、remember/promote/dream 扫描、associate 分片索引等）写在手册与代码里，**不在此重复「已落地」叙事**。

## 阅读顺序

| 文件 | 内容 |
| --- | --- |
| [00-first-principles.md](00-first-principles.md) | 过滤准则（做什么 / 不做什么） |
| [01-comparison.md](01-comparison.md) | 竞品机制证据（借鉴用） |
| [02-borrow.md](02-borrow.md) | 借鉴 / 有条件 / 拒绝 |
| [03-optimizations.md](03-optimizations.md) | 待办项总表 |
| [04-specs.md](04-specs.md) | 待办项实现细则 |
| [05-weight-design.md](05-weight-design.md) | Tag weight 数学（支撑 O1） |
| [06-o1-o3-decision.md](06-o1-o3-decision.md) | O1–O3 落地裁定（已实现） |

选型打分与第一性原理对照见 [../assessments/oss-comparison.md](../assessments/oss-comparison.md)（主观评价；非跑分）。

## 建议落地顺序

```text
O1 weight→expand → O2 PPMI 建议 → O3 根骨架
  → O5 时间窗 → O9 dream 加深 → O8 渐进加载 → O6 半衰期 → O10 语义RRF
  → O11 evidence → O14 export → O13 MCP → O12 质量归档 → O15 extract → O16 canvas
```
