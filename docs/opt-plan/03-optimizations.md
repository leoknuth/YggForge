# 03 · 后续优化建议

> **原因 · 方案 · 效果**。细则见 [04-specs.md](04-specs.md)；权重数学见 [05-weight-design.md](05-weight-design.md)。  
> 行为闸门 / channel 等**已具备能力**见 [../reference/behavior-config.md](../reference/behavior-config.md)，不在此复述。

## 总览

| ID | 项 | 优先级 | 状态 |
| --- | --- | --- | --- |
| O1 | weight 进入 expand | P0 | **已落地**（见 [06-o1-o3-decision.md](06-o1-o3-decision.md)） |
| O2 | 共现 PPMI 建议建边 | P0 | **已落地** |
| O3 | 根标签骨架 | P0 | **已落地** |
| O5 | 时间窗过滤 | P1 |
| O6 | 半衰期排序 | P1 |
| O8 | 渐进加载 | P1 |
| O9 | dream 管家增强 | P1 |
| O10 | 可选语义 + RRF | P1 |
| O11 | evidence 追溯链 | P1–P2 |
| O12 | 质量分/归档建议 | P2 |
| O13 | MCP 暴露 | P2 |
| O14 | export | P2 |
| O15 | extract 模板对接 | P2 |
| O16 | TaskCanvas | P2 |

---

## O1 · Tag weight 进入 expand（P0）

**原因**  
YAML 已有 `weight`，但 expand 丢弃 → 强边弱边同等污染 BFS。

**方案**  
`w∈[0,1]`；代价 `cost=-ln(w)`；路径强度 `∏w`；`w<min_expand` 不扩。配置进 `graph.defaults.json`。

**效果**  
同跳强边优先；弱边不再渗流。

---

## O2 · 共现 PPMI 建议建边（P0）

**原因**  
图太稀则联想临界难过；按频率连边会被热门 tag 淹没。

**方案**  
扫 front matter → `tag-suggestions.json`；`--apply` 经 behavior 闸门；建议 weight 封顶约 0.65。

**效果**  
密度↑、孤岛↓；权威边仍人审可控。

---

## O3 · 最小根标签骨架（P0）

**原因**  
少量根边显著降低连通临界；冷启动否则 associate 几乎只有种子自身。

**方案**  
手补 `tag-graph.yaml` + synonyms：工程向根互相可达。

**效果**  
新仓也能跨域跳到邻近制度/经验区。

---

## O5 · 时间窗过滤（P1）

**原因**  
「上周教训 / 本月决策」是工程刚需。

**方案**  
`recall` / `dream`：`--after` / `--before`；优先 front matter 时间，回退 mtime。

**效果**  
时间线可查；dream 可做「本周晋升池」。

---

## O6 · 半衰期排序（P1）

**原因**  
纯相关度抬升陈旧 observation；制度不应随时间淡出。

**方案**  
`score *= 0.5**(age/half_life)`；observation 短、lesson 中、**rule 关闭衰减**。

**效果**  
新近经验优先；章程稳定。

---

## O8 · 渐进加载（P1）

**原因**  
Token 贵；写入钉死层会伤跨域 → **只在查询时分层**。

**方案**  
L0 标题/根 tag → L1 摘要 → L2 按需全文；`--budget-tokens` / `--progressive`。

**效果**  
上下文更省。

---

## O9 · Dream 管家增强（P1）

**原因**  
现 dream 主要是 duplicate + 晋升扫描；缺主题簇 / 孤岛 / 晋升理由等管家信息。

**方案**  
报告追加共现 Top-N、可选社区簇、晋升理由模板、孤岛 tag；写 runtime；**禁止自动 promote**。

**效果**  
一份报告驱动人工 promote / relate。

---

## O10 · 可选语义 + RRF（P1）

**原因**  
关键词有盲区；默认不能被向量库绑架。

**方案**  
`features.semantic_retrieval` 默认 false；开启后 tag 序 + BM25 + 向量 → RRF；无模型降级。

**效果**  
同义召回↑；轻量安装仍可跑。

---

## O11 · evidence 追溯链（P1–P2）

**原因**  
晋升无证据则不可审、难回滚叙事。

**方案**  
schema `evidence[]`；promote 从 observation 拷贝；dream 标缺证据候选。

**效果**  
晋升可审、可追溯。

---

## O12 · 质量分与归档建议（P2）

**原因**  
仓膨胀降熵；需要「建议归档」而非静默删真源。

**方案**  
runtime 统计 + 建议分；归档提案；删/移 core 走 ask。

**效果**  
表层高信号，历史可沉。

---

## O13 · MCP 暴露（P2）

**原因**  
跨 IDE/Agent 调用真源与联想是真痛点。

**方案**  
可选 MCP：associate / recall / remember / dream(status)；写操作走 behavior。

**效果**  
多工具共用制度+联想。

---

## O14 · 导出（P2）

**原因**  
人要用 Obsidian 等双链 UI。

**方案**  
`ygg export --format obsidian|plain|graphrag-input`；只读。

**效果**  
互操作↑，不改真源模型。

---

## O15 · 模板 extract 对接（P2）

**原因**  
外部抽取工厂与 ingest/distill 互补。

**方案**  
外部输出 → `sources/inbox`；合并默认 prefer_existing。

**效果**  
inbox 结构化↑，本仓仍做人审 OS。

---

## O16 · TaskCanvas（P2）

**原因**  
长任务过程摘要可降 Token；不应污染 knowledge。

**方案**  
过程摘要 + refs 仅 `yggforge-runtime`；进 knowledge 必须 promote。

**效果**  
会话噪音外置，制度层干净。

---

## 建议顺序

```text
O1 → O2 → O3
  → O5 → O9 → O8 → O6 → O10
  → O11 → O14 → O13 → O12 → O15 → O16
```

## 明确不做

- 默认强制重型记忆栈依赖  
- 静默回写权威 weight / 自动改 rules  
- 用会话记忆榜单替换工程可审 KPI  
