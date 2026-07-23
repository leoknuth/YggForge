# 01 · 项目实证比对（仓库 + 文档）

> 证据来源：各仓 README / 官方文档站点 + GitHub API（2026-07-22）+ 本仓代码实勘。  
> 分数为主观对齐，非跑分。

## 1. 赛道总表

| 项目 | 赛道 | 存储范式 | 检索范式 | 与本仓关系 |
| --- | --- | --- | --- | --- |
| **YggForge（本仓）** | 工程知识 OS + 轻量联想 | Git MD/YAML | tag BFS + 关键词 | — |
| GraphRAG | 语料 Graph RAG | 索引表 + 向量 | Global/Local/DRIFT/Basic | 互补 |
| Hindsight | 学习型 Agent 记忆 | PG + 图/时序索引 | TEMPR 四路 + RRF | 互补 |
| OpenViking | Context DB | AGFS 文件树 + 向量 | 目录递归 + intent + rerank | 思想可借 |
| TencentDB-Agent-Memory | 分层 Agent 记忆插件 | MD 上层 + DB 下层 | 金字塔下钻 | 思想可借 |
| Hyper-Extract | 提取工厂 | Knowledge Abstract | 多引擎抽取 | 挂 ingest |
| Mem0 | 通用 memory API | 向量/可选图 | add/search | 互补 |
| Memary | 实验记忆层 | Neo4j + stream | 图记忆原型 | 学习用 |
| Obsidian | PKM 壳 | 本地 MD vault | 双链/插件 | 人机 UI |
| Memmy 类 | 跨工具偏好同步 | 桌面扫历史 | 注入 | 互补 |

---

## 2. 逐项：机制 · 证据 · vs YggForge

### 2.1 microsoft/graphrag（~35k⭐ · MIT）

**官方机制（文档核实）：**

- Index：Documents → TextUnits → Entity/Relationship/Claim → Leiden 社区 → Community Reports → Embeddings  
- Query：Global（社区摘要）/ Local（实体邻域）/ DRIFT / Basic（向量）  
- 工厂模式：storage / cache / vector / LLM 可插拔  
- 警告：indexing **昂贵**；官方定位 methodology demo

**vs 本仓：**

| | GraphRAG | YggForge |
| --- | --- | --- |
| 图含义 | LLM 抽实体关系 | 人/半自动 **tag 邻接 + related** |
| 真源 | 索引产物 | Git 可审 Markdown |
| 成本 | 高 | 低 |
| 适合 | 私有语料全局问答 | 规范/错题/投影 |

**可借鉴（机制级）：** 社区报告作 dream 主题簇；claim/provenance → evidence；**勿内嵌全量索引管线为默认**。

---

### 2.2 vectorize-io/hindsight（~19k⭐ · MIT）

**官方机制（README + docs 核实）：**

- 三操作：`retain`（LLM 抽事实/实体）/ `recall`（TEMPR：语义+BM25+图+时间，融合）/ `reflect`（带 disposition 推理）  
- 部署：Docker + Postgres（或外部 PG）；LLM Wrapper 两行接入  
- 叙事：学习而非只存历史；LongMemEval 等公开成绩

**vs 本仓：**

| | Hindsight | YggForge |
| --- | --- | --- |
| 目标 | Agent 越用越懂 | 制度可审 + 轻量联想 |
| 写入 | 自动抽取进记忆库 | remember / promote 门禁 |
| 检索 | 四路融合 | 关键词 + tag hop（weight 未用） |
| 运维 | 服务+DB | 文件+脚本 |

**可借鉴：** 多策略召回 + **RRF**；时间维；reflect≈加深版 dream（**只出报告，不改 rules**）；budget/max_tokens≈渐进加载预算。

---

### 2.3 volcengine/OpenViking（~27k⭐ · AGPL-3.0）

**官方机制（FAQ/概念文档核实）：**

- 文件系统范式 + `viking://` URI；Resource / Memory / Skill  
- **写入时**生成 L0 `.abstract`（~100 tok）/ L1 `.overview`（~2k）/ L2 原文；查询渐进加载  
- 检索：目录递归 + intent（`search`）/ 简单 `find`；分数含父目录传播  
- 依赖 embedding（可 ollama）；AGPL **拷代码需合规**

**vs 本仓：**

| | OpenViking | YggForge |
| --- | --- | --- |
| 统一对象 | 记忆+资源+技能进 AGFS | 知识真源与 runtime 记忆分目录 |
| 层 | 写入钉死 L0/L1/L2 文件 | 制度目录分层；联想靠 tag |
| License | AGPL | PolyForm Noncommercial 1.0.0（商用另议） |

**可借鉴：** **渐进加载思想**（标题/摘要/正文）；检索轨迹可观测；**不要**把 AGFS/强制 embedding 当默认，**不要**用写入钉死层替代 tag 跨域联想。

---

### 2.4 TencentCloud/TencentDB-Agent-Memory（~9k⭐ · MIT）

**官方机制（README 核实）：**

- 双支柱：**符号短期记忆**（工具日志 offload → Mermaid canvas + `node_id` 回指 refs）+ **长期金字塔** L0 对话→L1 原子→L2 场景→L3 画像  
- 「下层保证据，上层保结构」；白盒下钻  
- 主集成 OpenClaw；Node≥22；给 Token/通过率数据

**vs 本仓：**

| | TencentDB | YggForge |
| --- | --- | --- |
| 短期 | TaskCanvas 符号图 | 无（过程噪音仍可能进对话） |
| 长期 | 固定四层提炼 | rules/lessons/… + promote |
| 存储 | MD 上层 + DB 下层 | 全文件优先 |

**可借鉴：** evidence/`node_id` 追溯；TaskCanvas **落 runtime**；分层提炼**思想**对齐 promote 链（observation→lesson→rule），**勿**强制 SQLite 金字塔替代 Git 制度仓。

---

### 2.5 yifanfeng97/Hyper-Extract（~3k⭐ · Apache-2.0）

**官方机制（README 核实）：**

- CLI `he`：非结构化 → Knowledge Abstract（List/Model/KG/超图/时空图）  
- 10+ 引擎、80+ YAML 模板；增量进化；**Obsidian 导出**；**MCP `he-mcp`**；True Mean Embedding

**vs 本仓：** 对方是提取工厂；本仓是 OS。应对接 `ingest`/`distill`，产物进 sources，再晋升。

**可借鉴：** 模板 Schema、增量合并策略、Obsidian 导出、可选 MCP；超图非 P0。

---

### 2.6 mem0ai/mem0（~61k⭐ · Apache-2.0）

**官方机制（AGENTS.md / 站点核实）：**

- `add` / `search` / `update` / `history`；User/Session/Agent 多层  
- OSS SDK + 自托管 server + Cloud；可选 Graph Memory、MCP

**vs 本仓：** Mem0 管个性化事实碎片；本仓管「该怎么做」。可并行：`remember` 写 observation，同时可选同步 Mem0。

---

### 2.7 其它

| 项目 | 核实要点 | vs 本仓 |
| --- | --- | --- |
| **Memary** | Neo4j + Memory Stream 实验 | 学结构，不生产制度 |
| **Obsidian** | 闭源应用 + 开放 vault 格式 | 导出 `[[wikilinks]]`；真源仍 Git |
| **Memmy 类** | 跨工具偏好同步产品 | MCP 暴露本仓后部分可替代「同步面」 |

---

## 3. 本仓 YggForge（代码实勘）

| 维度 | 现状 |
| --- | --- |
| 布局 | `yggforge-core` / `generated` / `runtime` |
| CLI | 15 显式动作 + 自然语言路由 |
| 联想 | associate：expand(hop)→tag 反查并集→related；**weight 未进 expand** |
| 记忆 | remember（tags/title_refined）→ raw + 可选 lessons inbox；dream 扫描报告；promote 门禁 |
| 写闸 | core_write：allow/ask/deny/warn/audit/dry_run |
| 缺 | channel、时间窗、共现 suggest、渐进加载、语义 RRF、MCP |

**独特优势（竞品难替代）：** Git 可审制度真源 × 多 Agent 整包投影 × 人审晋升 × 去中心化 tag 联想潜能 × 十年可读格式。

---

## 4. 六维雷达（实证纠偏后，沟通用）

| 维度 | GraphRAG | Hindsight | OpenViking | TencentDB | Hyper-Ex | Mem0 | Obsidian | **本仓** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 智能自动化 | 9 | 10 | 8 | 8 | 9 | 8 | 1 | 6 |
| 检索深度 | 9 | 9 | 8 | 6 | 7 | 8 | 5 | 6 |
| 可维护性 | 3 | 4 | 5* | 6 | 7 | 4 | 10 | **9** |
| 使用门槛 | 2 | 3 | 4 | 7 | 6 | 7 | 9 | **8** |
| 独特价值 | 7 | 9 | 8 | 8 | 8 | 7 | 8 | **8** |
| 生态 | 9 | 7 | 8 | 7 | 6 | **10** | 9 | 4 |
| **约分** | 6.8 | 7.4 | 6.7 | 7.0 | 7.4 | 6.9 | 7.2 | **~7.0** |

\* OpenViking：文件范式可维护，但 AGPL + embedding/Rust 绑定拉低「十年纯文本可搬迁」分。

---

## 5. 组合架构（推荐）

```text
人：Obsidian ↔ Git 真源（本仓 knowledge/）
Agent：deploy → ~/.*/yggforge-core（本仓 core）
会话碎片（可选）：Mem0 / Hindsight
大语料（可选）：GraphRAG export/import 边界清晰
抽取（可选）：Hyper-Extract → sources/inbox → distill → promote
跨工具（可选）：本仓 MCP 或 Memmy 类
```
