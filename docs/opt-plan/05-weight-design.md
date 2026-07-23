# 05 · Tag Weight 详细设计

> weight / 扩跳数学与语义。待办实现见 [03-optimizations.md](03-optimizations.md) / [04-specs.md](04-specs.md)（O1）。  
> 相关：[../concepts/memory-and-association.md](../concepts/memory-and-association.md)

## 目录

- [1. 设计目标与约束](#1-设计目标与约束)
- [2. Weight：语义、范围与强弱](#2-weight语义范围与强弱)
- [3. 多跳加总与扩跳算法](#3-多跳加总与扩跳算法)
- [4. Weight 的维护与更新](#4-weight-的维护与更新)
- [5. 多类型权重（可选扩展）](#5-多类型权重可选扩展)
- [6. 其它优化项](#6-其它优化项)
- [7. 配置草案与建议实现顺序](#7-配置草案与建议实现顺序)
- [8. 参考资料](#8-参考资料)

---

## 1. 设计目标与约束

| 目标 | 说明 |
| --- | --- |
| 可解释 | 人打开 `tag-graph.yaml` 能读懂「谁和谁更近」 |
| 可审 | 权威边权进 Git；统计与建议进 generated/runtime |
| 轻量 | 默认无 GPU / 向量库；图规模百级 tag 时 O(E) 可接受 |
| 渐进 | 现网边几乎全是 `weight: 1.0`，升级不能一夜打乱联想 |

**约束（与仓库底线一致）：**

- 真源只在 `yggforge-core/graph/tag-graph.yaml`
- 程序不得静默改写权威 weight（除非显式 `--apply` + 人确认策略）
- 增强能力默认关闭或 dry-run

---

## 2. Weight：语义、范围与强弱

### 2.1 采用什么语义？

业界常见两种相反约定：

| 约定 | 含义 | 典型用途 |
| --- | --- | --- |
| **强度 / 置信度**（越高越强） | 关系有多可靠、多相关 | 不确定知识图谱、graph-memory、Cognee 记忆权重 |
| **代价 / 距离**（越高越远） | 走这条边有多贵 | Dijkstra、路网、最短路 |

本仓 tag 图是**联想相关度**，不是路网代价，因此采用：

> **`weight` = 关联强度（association strength）**  
> **数值越大 → 关系越强**  
> **数值越小 → 关系越弱**

扩跳内部需要「代价」时，再做单调变换（见 §3），不要把代价语义写进 YAML。

### 2.2 取值范围

| 项目 | 规定 |
| --- | --- |
| 类型 | `float` |
| 闭区间 | **`[0.0, 1.0]`** |
| 缺省（YAML 省略） | **`0.70`**（显式中强；不要默认 1.0，避免「全部满分」无法区分） |
| 写入校验 | `< 0` 或 `> 1` → 报错拒绝；NaN 拒绝 |
| 扩跳门槛 | **`w < w_min_expand`（默认 `0.15`）视为不扩跳**（边可保留在 YAML 供人工查看） |

> 参考：graph-memory 使用 `[0,1]` 并分档；可视化工具常把任意区间归一化到 `[0,1]`；不确定 KG 用置信度 ∈ (0,1]。  
> PLOS One 提醒：同一数值在不同局部网络里「强弱」可能不同——因此本仓用**全局分档 + 建议层 backbone（共现阈值）**，而不是只看裸数值。

### 2.3 分档语义（写进文档与 CLI 帮助）

| 区间 | 档位 | 含义 | 谁该写 |
| --- | --- | --- | --- |
| `0.00 – 0.14` | 可忽略 | 噪声 / 待删；默认不扩跳 | 建议层或人工标记 deprecate |
| `0.15 – 0.34` | 弱 | 偶发共现、弱相关领域 | 共现建议冷启动 |
| `0.35 – 0.54` | 中弱 | 有关联但不稳定 | 建议确认后 |
| `0.55 – 0.74` | 中强 | 稳定相关；**新人工边默认落此档** | 人 / `ygg tag` |
| `0.75 – 0.89` | 强 | 明确同族或高频工作流 | 人确认多次 |
| `0.90 – 1.00` | 极强 | 近同义 / 核心工作流轴 | 谨慎；留给 synonym 或核心轴 |

**示例（意图，非强制现网值）：**

- `cpp ↔ hpc` ≈ `0.85`（强）
- `cpp ↔ formatting` ≈ `0.55`（中强）
- `rust ↔ coffee` ≈ `0.10`（弱，不应扩跳）

### 2.4 与现网 `1.0` 的兼容策略

当前根轴已校准到 `0.60–0.85`，演示域（coffee/shell/caracal）暂留 `1.0`（见 `06-o1-o3-decision.md`）；`1.0` 表示「未校准的强边或近同义」，不再等于「无权重」。

| 阶段 | 策略 |
| --- | --- |
| A. 兼容期 | 算法启用 weight；`1.0` 合法且表示「未校准的强边」 |
| B. 校准期 | `ygg tag --suggest` / 文档引导把核心轴留在 `0.85–1.0`，次要边降到 `0.55–0.75` |
| C. 稳态 | 新边默认 `0.70`；`1.0` 仅用于近同义或人显式指定 |

迁移不强制批量改 YAML；允许渐进。

### 2.5 无向还是有向？

- YAML 现状是**有向邻接**（`A.related → B` 不自动蕴含反向）。
- 联想语义上默认按**无向**使用更符合人类标签：扩跳时若只有 `A→B`，应视同可走 `B→A`，除非将来加 `directed: true`。
- **实现建议：** `TagGraph.load` 构建对称邻接（取 `max(w_ab, w_ba)`）；权威文件仍可只写一侧，另一侧由加载器补全到内存图。  
- 写回 YAML 时仍只改用户编辑的一侧，避免双向刷文件。

---

## 3. 多跳加总与扩跳算法

### 3.1 问题定义

给定种子 tags `S`，在 hop ≤ `H`、节点数 ≤ `N` 约束下，得到：

1. 扩展 tag 集合及其「多近」  
2. 再映射到 knowledge 条目排序（`ygg associate`）

「多近」必须同时考虑：**跳数** 与 **边强度**。

### 3.2 单边：强度 → 代价

对边权 `w ∈ (0, 1]`：

```text
cost(e) = -ln(max(w, ε))     # ε = 1e-6，避免 log(0)
```

性质：

- `w → 1` ⇒ `cost → 0`（几乎免费）  
- `w → 0` ⇒ `cost → +∞`（极贵）  
- 与「强度越大越好」单调一致  

弱边若 `w < w_min_expand`，直接不入邻接（扩跳视角）。

### 3.3 路径加总（核心公式）

对路径 `P = e1, e2, …, ek`：

**强度乘积（主语义，推荐对外解释）：**

```text
strength(P) = ∏_{e ∈ P} w(e)
```

**代价加总（主计算，便于最优路径）：**

```text
cost(P) = Σ_{e ∈ P} cost(e) = -ln(strength(P))
```

因此：**多级 weight 的加总 = 路径上强度相乘（等价于代价相加）。**  
不要对 `w` 做算术平均当路径分——会低估长链上的弱边风险。

种子自身：

```text
strength(seed) = 1.0
cost(seed) = 0.0
hop(seed) = 0
```

### 3.4 节点得分（多条入路时）

同一 tag `t` 可能经多条路径到达，取**最优**：

```text
cost*(t)     = min over paths  cost(P)
strength*(t) = exp(-cost*(t))
hop*(t)      = 该最优路径的跳数（并列时取跳数更小者）
```

若只要「是否可达」：`cost* < ∞` 且 `hop* ≤ H`。

### 3.5 推荐算法：分层约束 + 加权最优（非朴素 BFS）

纯 BFS 只认跳数，会忽略 weight（现状问题）。全量 Dijkstra 在百级节点上没问题，但联想更关心「先跳数、再强度」。

**推荐：Hop-constrained best-path（带 hop 上限的最优代价）**

```text
状态键：(node, hop)
优先队列按 cost 升序
松弛：若 hop+1 ≤ H 且 new_cost < best[node]（在 hop 约束下）则更新
剪枝：节点数达到 N 时停止扩展新节点（已在队内的可算完）
```

复杂度：O((V·H + E·H) log(V·H))，对本仓可忽略。

**P0 简化版（若先求改动最小）：**

1. 仍用 hop-BFS 得到候选集合（但跳过 `w < w_min_expand`）  
2. 对候选边上再跑一遍「仅在候选子图」的代价松弛  
3. 排序键：

```text
order_key(t) = (hop*(t), cost*(t), tag_name)
```

即：**先近跳，同跳比强度（代价小者优先）**。

### 3.6 条目级分数（associate 排序）

条目命中多个扩展 tag 时（反查表合并）：

```text
tag_score(entry) = max_{t ∈ tags(entry) ∩ expanded}  strength*(t) * hop_decay^hop*(t)
```

建议默认 `hop_decay = 0.75`（每多一跳，强度再打七五折，与乘积强度叠加）。

若同时有关键词/标题命中（未来混合检索），用 RRF（见 §6.3），**不要**把 BM25 与 `strength*` 直接线性加权。

### 3.7 数值算例

```text
种子: cpp
边: cpp --0.9--> hpc --0.6--> performance
    cpp --0.5--> formatting

路径 A: cpp→hpc→performance
  strength = 0.9 * 0.6 = 0.54
  hop = 2

路径 B: cpp→formatting
  strength = 0.5
  hop = 1

排序：formatting (hop1, 0.50) 先于 performance (hop2, 0.54)
同 hop 时再比 strength。
```

---

## 4. Weight 的维护与更新

### 4.1 三层数据与 core 写入策略

| 层 | 位置 | 内容 | 谁写 |
| --- | --- | --- | --- |
| **权威边** | `yggforge-core/graph/tag-graph.yaml` | `tag` + `weight` | 脚本按策略写入 / 人编辑 |
| **建议** | `yggforge-generated/indexes/tag-suggestions.*` | 共现、PPMI、建议 weight | `graph build` / `tag --suggest` |
| **运行统计** | `yggforge-runtime/cache/tag-stats.json`（可选） | hit、last_used | associate/recall 可选记 |

对 core 真源的常见修改**不再一律人工确认**，而由配置决定：

- 配置：`yggforge-core/config/core_write.defaults.json`（本机可用 `yggforge-runtime/config/core_write.local.json` 覆盖）
- 模式：`allow` / `ask` / `deny` / `warn` / `audit` / `dry_run`（详见 [../behavior-config.md](../reference/behavior-config.md)）
- 默认：`tag_weight_update` / `tag_relate` / `tag_add` 为 **allow**；批量 `tag_suggest_apply` 为 **ask**

原则：自动衰减仍不默认回写权威文件；批量共现建议默认 ask；单次 weight/relate 可按配置放行。

### 4.2 边的来源 → 初始 weight

| 来源 | 初始 `weight` | 说明 |
| --- | --- | --- |
| 人工编辑 / `ygg tag --relate` | `0.70`（可改） | 默认中强 |
| 同义词表（`tag-synonyms.yaml`） | `0.95`（若落边） | 近同义极强 |
| 共现建议（首次） | 由 PPMI 映射到 `[0.25, 0.65]` | 不得自动写权威 |
| 传播建议（propagate） | `0.40` 起 | 仅建议 |
| 用户确认建议 `--apply` | `max(建议, 0.55)` | 进入中强档 |

### 4.3 更新公式（仅对「已进入权威」的边）

**A. 确认增强（人确认或显式 reinforce）：**

```text
w ← min(1.0, w + Δ_confirm)     # 默认 Δ_confirm = 0.10
```

**B. 证据上限（建议分数更高时，防降级）：**

```text
w ← max(w, w_evidence)          # 用于 --apply 且建议 > 当前
```

**C. 人工降权 / 删除：**

- 人改 YAML 或 `ygg tag --relate ... --weight 0.2`  
- `w < w_min_expand` 即停止扩跳，可保留作「已否决弱边」

**D. 禁止默认启用的：按命中次数自动 +Δ**

- 易形成马太效应（PLOS / 记忆系统常见坑）  
- 若将来要做，只写 runtime stats，**定期出报告**，由人决定是否 `--apply` 一批

### 4.4 共现 → 建议 weight（PPMI）

对条目集合，统计 tag 共现（同一 front matter `tags` 内）：

```text
PMI(a,b)  = log2( P(a,b) / (P(a)P(b)) )
PPMI(a,b) = max(PMI(a,b), 0)
```

约束：

- `count(a,b) ≥ min_cooccur`（默认 3）才建议  
- 过滤超高频万能 tag（可配置 denylist / IDF 下限）

映射到建议强度：

```text
w_suggest = clamp(
  w_cooccur_min + (w_cooccur_max - w_cooccur_min) * tanh(PPMI / τ),
  0.0, 1.0
)
```

默认：`w_cooccur_min=0.25`，`w_cooccur_max=0.65`，`τ=2.0`。  
**共现边天花板 0.65**：避免统计边压过人工强边。

### 4.5 时间衰减（权威边默认关闭）

记忆系统常用：

```text
decay = 0.5 ** (age_days / half_life_days)
effective = max(w * decay, w * floor)    # floor 如 0.7，防止归零
```

对本仓 **tag 权威边**：

- **默认不对 `tag-graph.yaml` 做时间衰减**（制度性关联不应「过期消失」）  
- 若启用，只作用于 **runtime 有效强度** 或 **observation 记忆条目**，不回写 YAML  

对 **recall 条目排序** 可用半衰期（见 §6.2）。

### 4.6 CLI / 流程（建议）

```text
ygg tag --suggest              # 写 generated 建议，含 w_suggest
ygg tag --suggest --apply      # 交互或 --yes：按 B/C 规则合并进 yaml
ygg tag --relate a b --weight 0.8
ygg associate --tag cpp        # 使用 §3 算法
ygg graph build                # 可附带导出共现矩阵摘要
```

审计：每次 `--apply` 在 generated 留 diff 摘要（from→to）。

---

## 5. 多类型权重（可选扩展）

Cognee 等支持边上多权重字典。本仓 **v1 只暴露标量 `weight`**；需要时再扩展：

```yaml
related:
  - tag: hpc
    weight: 0.82          # 对外合成强度（权威）
    weights:              # 可选分解，默认不写
      manual: 0.80
      cooccur: 0.55
      synonym: 0.0
```

合成（若启用分解）：

```text
weight = clamp(
  α * manual + β * cooccur + γ * synonym,
  0, 1
)
```

默认 `α=0.7, β=0.3, γ=0.0`（同义词走 synonyms 表时 γ 可升）。  
**未配置 `weights` 时，`weight` 即为唯一真值。**

---

## 6. 其它优化项

> 见 [03-optimizations.md](03-optimizations.md) / [04-specs.md](04-specs.md)。
> 本文件只保留 §2–§5 的 weight 数学与维护约定；落地状态勿在此双维护。

---

## 7. 配置草案与建议实现顺序

### 7.1 `config/graph.defaults.json` 增补（示意）

```json
{
  "default_hop": 2,
  "max_tag_nodes": 64,
  "entry_related_hops": 1,
  "weight": {
    "default_edge": 0.7,
    "min_expand": 0.15,
    "hop_decay": 0.75,
    "epsilon": 1e-6,
    "undirected_load": true
  },
  "suggest": {
    "min_cooccur": 3,
    "ppmi_tau": 2.0,
    "w_cooccur_min": 0.25,
    "w_cooccur_max": 0.65,
    "delta_confirm": 0.1
  },
  "time": {
    "half_life_days": {
      "observation": 60,
      "lesson": 365,
      "rule": null
    }
  },
  "hybrid": {
    "enabled": false,
    "rrf_k": 60
  }
}
```

### 7.2 建议实现顺序

| 阶段 | 交付 | 预估 |
| --- | --- | --- |
| P0-a | expand 用 weight + 路径 strength/cost；JSON 暴露字段 | 小 |
| P0-b | 共现 PPMI 建议报告；文档分档；默认新边 0.7 | 小–中 |
| P1-a | `--after/--before` + 可选半衰期排序 | 中 |
| P1-b | 可选向量 + RRF（默认关） | 中–大 |
| P2 | dream 报告加深、export、质量建议 | 按需 |

### 7.3 明确不做

- 权威边上的自动时间衰减回写  
- 按点击率静默升权  
- 默认启用云端 embedding  
- 把共现边直接写成 `1.0`  

---

## 8. 参考资料

1. graph-memory Weight System（`[0,1]` 分档、boost / confidence-max）：社区 Graph Schema 实践  
2. Cognee Memory Weights：边上多权重、强度语义  
3. PLOS One *How strong is strong?*：边权局部相对性 → 需阈值/backbone，忌裸读数值  
4. 加权图最短路：代价可加；强度宜用 `-ln(w)` 转代价后求和  
5. PMI / PPMI：共现关联强度；需最小频次抑制罕见词爆表  
6. Elasticsearch / Azure AI Search RRF：`score = Σ 1/(k+rank)`，融合异质检索器  
7. Half-life decay RAG / Agent memory：`0.5 ** (age/half_life)`；强化用 reinforced 时间而非被动访问  

---

## 附录 A：对外一句话规范（可贴进 tag-graph 头注释）

```text
weight ∈ [0.0, 1.0]，越大表示关联越强。
路径强度 = 沿途边权之积；扩跳忽略 < 0.15 的边。
权威 weight 仅人工或 ygg tag --apply 可改；统计与建议在 generated/runtime。
```

## 附录 B：与 Kimi 分析文的对齐

| Kimi 建议 | 本文落点 |
| --- | --- |
| 启用 weight | §3 |
| 加权 BFS / 按 weight 排序 | §3.5（升级为 hop 约束最优代价） |
| 共现建议 | §4.4 |
| 时间感知 | §4.5（权威边默认关闭）；条目级见 [03-optimizations.md](03-optimizations.md) O5/O6 |
| 可选语义 | [03-optimizations.md](03-optimizations.md) O10 |
| 保持轻量 | §1、§7.3 |
