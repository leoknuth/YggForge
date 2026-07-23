# 02 · 值得借鉴与拒绝照搬（实证过滤）

> 过滤准则见 [00-first-principles.md](00-first-principles.md)。  
> 每条标注：**来源仓库证据** → **本仓落点**。

## 1. 强烈推荐（过四问）

| # | 机制 | 来源证据 | 本仓落点 | 为何过筛 |
| --- | --- | --- | --- | --- |
| B1 | **边权参与图遍历/排序** | 本仓 yaml 已有 weight；Hindsight/图系统普遍区分强弱 | `knowledge/tag_graph.py`（`TagGraph.expand`） | 零新依赖；补半成品 |
| B2 | **共现→建议边（PPMI）** | 标签推荐经典；原文自研项 | `ygg tag --suggest` → generated；apply+core_write | 增密度且可审 |
| B3 | **多策略召回 + RRF** | Hindsight TEMPR；ES/Azure RRF 文档 | 可选：tag / keyword / vector → RRF | 默认关；不绑架安装 |
| B4 | **时间维** | Hindsight temporal；本仓缺 `--after` | recall/dream 时间窗 + 分层半衰期 | 刚需；rules 不衰 |
| B5 | **渐进加载（查询时）** | OpenViking L0/L1/L2 **思想**；Hindsight budget | associate/recall：标题→摘要→正文 + token 预算 | 借思想不借 AGFS |
| B6 | **白盒 evidence / node_id** | TencentDB「下层证据上层结构」 | front matter `evidence`；promote 建议必填 | 高熵；可审 |
| B7 | **符号短期压缩落 runtime** | TencentDB Mermaid canvas + refs | `yggforge-runtime/.../canvas` | 不污染 knowledge |
| B8 | **社区/主题簇报告** | GraphRAG Leiden+Community Report | dream 报告块（可选 networkx） | 只报告；不改 rules |
| B9 | **模板化抽取 + Obsidian 导出** | Hyper-Extract `he` + export + MCP | ingest/distill；`ygg export` | 工厂挂接 OS |
| B10 | **MCP 暴露记忆/检索** | Mem0 MCP；Hyper `he-mcp`；Hindsight skills | 可选 ygg MCP | 跨工具用真源 |

---

## 2. 有条件借鉴

| 机制 | 条件 |
| --- | --- |
| GraphRAG 全量实体抽取 | 仅 offline / 大语料；结果进 sources；成本明示 |
| Hindsight reflect | 作为「深度问答」可选服务，**不**替代 promote |
| OpenViking 目录递归检索 | 可对 `knowledge/` 做 intent 路由（rules vs lessons），需 LLM 时默认关 |
| Mem0 add/search | 并行会话层；禁止把 Mem0 当 rules 真源 |
| 权重 hit_count 反馈 | **只写 runtime**；回写权威边必须 core_write allow/audit，禁静默 +0.01 |
| 超图 | P3；二部 tag 边未扎实前不做 |

---

## 3. 拒绝照搬

| 拒项 | 原因 |
| --- | --- |
| 默认 Docker+PG+强制云 LLM（Hindsight 整机） | 破轻量底线 |
| AGPL 代码直接拷入本仓（OpenViking） | 许可证风险；只借思想 |
| 写入时钉死唯一 L0–L3 目录替代 tag 网 | 伤害跨域联想；与制度分层混淆 |
| 全自动改 rules / 无门禁画像写章程 | 破晋升模型 |
| 内嵌 GraphRAG 为默认索引 | 成本与噪声；赛道错误 |
| 权威 tag 边按点击自动衰减回写 Git | 马太效应 + 污染真源 |
| 用 LongMemEval 分数当本仓 KPI | 评价错赛道 |
| 回退 skills/yggforge-memory 单框架树 | 已多 Agent 三层布局 |

---

## 4. 「涌现四前提」实证改写

| 原文 | 实证后本仓版 |
| --- | --- |
| 根标签骨架 | **要做**：工程向根边（与现有 tag-graph 对齐） |
| 自动共现建边 | **建议+apply**，非静默；默认 `tag_suggest_apply=ask` |
| 权重动态 | expand 用静态权威 weight（P0）；动态统计进 runtime（P1） |
| TaskCanvas | **P2 可选**，非涌现临界 |

临界定义：B1+B2+根骨架可用 → 联想质量明显改善，即可宣称「过临界」，不必等 MCP/超图。  
（写入策略 / channel 已由 behavior 配置承担，见手册，不列入本表待办。）
