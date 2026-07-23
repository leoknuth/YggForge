# YggForge 与相关项目对比（第一性原理）

> **权威正文。** HTML / Canvas 若存在，仅为预览副本，以本文为准。  
> 对比范围对齐 [../opt-plan/](../opt-plan/README.md) 中讨论过的项目；机制证据见 [../opt-plan/01-comparison.md](../opt-plan/01-comparison.md)。

## 目录

- [1. 目的与第一性原理](#1-目的与第一性原理)
- [2. 评分声明（必读）](#2-评分声明必读)
- [3. 问题空间：先分清再比较](#3-问题空间先分清再比较)
- [4. YggForge 自身（参照系）](#4-yggforge-自身参照系)
- [5. 逐项分析](#5-逐项分析)
- [6. 主观对照表](#6-主观对照表)
- [7. 组合建议](#7-组合建议)
- [8. 相关文档](#8-相关文档)

---

## 1. 目的与第一性原理

记忆 / 知识系统从认知与工程双侧收敛到两条（见 [../opt-plan/00-first-principles.md](../opt-plan/00-first-principles.md)）：

| 原理 | 含义 |
| --- | --- |
| **清晰高熵存储** | 每条资产边界清楚、可寻址、可追溯，不与其它条目糊成一团 |
| **高效检索 + 智能联想** | 不但「搜到」，还能「想到相关」 |

**YggForge 要回答的问题：**

- 团队规范 / 错题 / 决策如何 **Git 版本化**，并投影到多 Agent？
- 如何用人审门禁防止 Agent **静默改章程**？
- 如何用轻量 **tag 网**做人类式联想？

**YggForge 不主责：**

- 跨会话「越用越懂用户」的 SOTA 学习记忆  
- 百万文档语料的全局社区问答  
- 桌面级「扫所有 AI 工具历史」的偏好快递  

本文用上述参照系比较各项目的特点、优点、缺点；分数只作沟通辅助。

---

## 2. 评分声明（必读）

文中所有分数均为作者基于公开文档、仓库定位与本仓问题定义的**主观对齐评价**，用于：

- 快速建立「谁解决哪类问题」的心智模型  
- 讨论互补组合，而非宣布胜负  

**它们不是基准测试结果。**

更具体、可复现的评分，应使用专业评测协议，至少覆盖：

| 维度 | 示例度量 |
| --- | --- |
| 内存 / 磁盘 | 索引峰值 RSS、真源与生成物体量 |
| 耗时 | 冷启动、单次 recall/associate、全量重建索引 |
| Token 节约 | 同等任务下注入上下文的 token 数、渐进加载命中率 |
| 记忆能力 | 跨会话事实保持、冲突更新、时间一致性（如 LongMemEval 类） |
| 制度可审性 | 误晋升率、无门禁写 rules 次数、Git diff 可解释性 |
| 运维成本 | 依赖个数、是否强制 Docker/云 LLM、许可证约束 |

在未跑上述评测前，**不要用本文分数做采购或架构唯一依据**。

资料截止约 **2026-07**；星标与生态数据会变。

---

## 3. 问题空间：先分清再比较

| 问题空间 | 典型代表（本文） | 主要交付物 | 与 YggForge |
| --- | --- | --- | --- |
| 工程知识 OS | **YggForge** | 可审 Markdown + 晋升 + 多 Agent 投影 + tag 联想 | 同空间 |
| Agent 学习型 / 会话记忆 | Hindsight、Mem0、Memary | 自动抽取事实、多路检索、可选图 | **互补**为主 |
| 语料 Graph RAG | Microsoft GraphRAG | 实体/社区索引 + 全局问答 | 大库问答，非制度仓 |
| Context / 分层记忆运行时 | OpenViking、TencentDB-Agent-Memory | 文件系统或金字塔记忆、渐进加载 | 思想可借 |
| 抽取工厂 | Hyper-Extract | 非结构化 → 结构化 Abstract | 挂 `ingest` |
| PKM 壳 | Obsidian | 本地 vault、双链、可视化 | 人机 UI |
| 跨工具偏好同步 | Memmy 类 | 扫多工具历史并注入 | 同步面，非真源 |

---

## 4. YggForge 自身（参照系）

### 特点

- 真源：`yggforge-core`（Git Markdown / YAML）；生成物与本机态分目录  
- 联想：`tag-graph` BFS + `tag-inverted`（经条目 **id**）+ `related`  
- 闭环：`remember` → `dream` 扫描 → `promote` 门禁 → `graph build`  
- 投影：整包 `yggforge-core` → 各 Agent 家目录（薄入口叠加）；`project_to` 原生技能包生成尚未落地  
- 写闸：behavior / core_write（ask / allow / deny 等）  
- **插件智能管理**：`plugins/`（skill / mcp-server / hook / 插件侧 rule）可被 tag 联想发现，与 `knowledge/` 同源索引  
- **三源综合回答**：模型推理 + ygg 检索 + 联网；强制钩子按 action 路由（真源 `standing-preference`）  
- **项目级部署**：除 Agent 家目录外，可投影到工作区 / 项目路径（见 deploy 文档）

### 优点

- 十年可读格式；diff 可审；默认可无强制向量库 / Docker  
- 制度分层（rules / lessons / templates / decisions / reference）与联想图正交  
- 多 Agent 共用同一套规范与联想；跨 knowledge / plugins 的 tag BFS 可验证（如 caracal 彩蛋）  

### 缺点

- 会话级「越用越懂」弱于专用记忆栈  
- 检索默认偏结构 + 关键词；语义 / RRF / 时间窗等仍在 [opt-plan](../opt-plan/03-optimizations.md)  
- 生态与明星度远低于 Mem0 / GraphRAG  
- `project_to` → 各 Agent 原生 `SKILL.md` 等仍为规划字段，勿当作已实现能力  

> **导出物说明：** 同目录 HTML / Canvas 若与本 `.md` 不一致，**以本 Markdown 为准**；HTML/Canvas 滞后时需人工重导出。

### 主观场景分（仅沟通用）

| 工程知识真源拟合 | 会话持久记忆拟合 |
| ---: | ---: |
| **9 / 10** | **4 / 10** |

---

## 5. 逐项分析

下列「主观分」均为 1–10，维度定义见 §6；**再次强调：主观，非跑分。**

### 5.1 Microsoft GraphRAG

**特点**  
从文档语料抽取实体 / 关系 / Claim，Leiden 社区与 Community Reports，再做 Global / Local / DRIFT / Basic 查询。工厂式可插拔 storage / vector / LLM。官方定位偏 methodology，并警示 indexing **昂贵**。

**优点**

- 大语料「全局问题」能力强；社区摘要适合主题鸟瞰  
- 查询模式成熟，工程文档与示例丰富  
- MIT，可组合进离线管线  

**缺点**

- 索引成本高；真源是索引产物而非可审制度仓  
- 图含义是 LLM 抽实体，不是团队 tag 邻接  
- 不解决多 Agent 规范投影与晋升门禁  

**相对 YggForge**  
互补：大库问答用 GraphRAG；规范 / 错题仍用本仓。可借鉴社区报告作 `dream` 主题簇、claim→evidence；**勿**默认内嵌全量索引。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 9 | 9 | 2 | 3 | 4 |

---

### 5.2 Hindsight（vectorize-io）

**特点**  
学习型 Agent 记忆：`retain` / `recall` / `reflect`；TEMPR（语义 + BM25 + 图 + 时间）+ RRF；常见部署 Docker + Postgres；强调「学习而非只存历史」。

**优点**

- 多策略召回与时间维完整；公开评测叙事强  
- reflect / disposition 适合深度问答  
- 对「跨会话个性化」主责清晰  

**缺点**

- 默认服务栈重，与「纯文件 + Git」底线冲突  
- 自动写入事实库，不能替代人审章程  
- 运维与密钥面大于本仓  

**相对 YggForge**  
互补会话层；可借鉴 RRF、时间窗、budget 渐进加载、`reflect`≈加深版 `dream`（只报告）。**勿**整机替换真源。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 9 | 10 | 3 | 3 | 9 |

---

### 5.3 OpenViking（volcengine）

**特点**  
Context DB / AGFS 文件树范式；Resource / Memory / Skill；写入生成 L0 abstract / L1 overview / L2 原文；目录递归 + intent 检索；常依赖 embedding；**AGPL-3.0**。

**优点**

- 「渐进加载」思想清晰，利于省 Token  
- 统一 URI / 目录语义，轨迹可观测  
- 文件范式对「可读对象」友好  

**缺点**

- AGPL 直接拷贝有合规成本  
- 写入钉死 L0–L2 目录会伤跨域联想（与 tag 网正交目标冲突）  
- 常绑 embedding / 较重组件，轻量默认难  

**相对 YggForge**  
借**查询时**分层加载思想；不要借整套 AGFS，不要用写入层替代 tag 联想。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 8 | 8 | 4 | 4 | 7 |

---

### 5.4 TencentDB-Agent-Memory

**特点**  
双支柱：符号短期记忆（工具日志 offload → Mermaid canvas + `node_id` 回指）+ 长期金字塔（对话→原子→场景→画像）；「下层保证据，上层保结构」；主集成偏 OpenClaw。

**优点**

- evidence / 白盒下钻叙事强，可审性好  
- TaskCanvas 把过程噪音移出主对话，利于省 Token  
- 分层提炼与 promote 链思想可对齐  

**缺点**

- 固定金字塔不能直接替代 Git 制度分层  
- 集成面偏特定 Agent 生态  
- 长期层若落 DB，与「全文进 Git」策略需划界  

**相对 YggForge**  
借 evidence、`node_id`、canvas **落 runtime**；勿强制 SQLite 金字塔替换 `knowledge/`。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 7 | 6 | 8 | 6 | 5 | 8 |

---

### 5.5 Hyper-Extract

**特点**  
抽取工厂：非结构化 → Knowledge Abstract（List / Model / KG / 超图等）；多引擎与大量 YAML 模板；增量进化；Obsidian 导出；可选 MCP。

**优点**

- 输入侧结构化能力强，模板可复用  
- 导出 / MCP 便于挂接其它系统  
- Apache-2.0，作管线组件合适  

**缺点**

- 不做制度 OS、不做人审晋升  
- 抽取噪声需下游消化  
- 超图等高级形态对多数工程制度场景过重  

**相对 YggForge**  
上游工厂：输出进 `sources/inbox` → distill → promote。本仓做人审 OS。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 6 | 6 | 9 | 6 | 4 | 3 |

---

### 5.6 Mem0

**特点**  
通用 Agent 记忆 API：`add` / `search` / `update` / `history`；User / Session / Agent 多层；OSS + 自托管 + Cloud；可选 Graph Memory、MCP。生态最大档之一。

**优点**

- 接入成本低，生态与文档成熟  
- 适合个性化事实碎片的增删改查  
- 可与本仓并行，不强制互斥  

**缺点**

- 默认不是「团队章程真源」  
- 向量 / 托管路径会提高运维与隐私面  
- 可审晋升与多 Agent 投影非其主责  

**相对 YggForge**  
会话碎片可走 Mem0；`rules/` 仍只认本仓 + promote。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 8 | 8 | 6 | 3 | 9 |

---

### 5.7 Memary

**特点**  
实验向记忆层：Neo4j + Memory Stream / Entity Knowledge Store 等；偏研究原型。

**优点**

- 图 + 流式记忆结构清晰，适合学习架构  
- 小而可拆，便于读源码  

**缺点**

- 生产制度仓能力不足  
- 依赖图数据库，轻量默认难  
- 维护与生态弱于 Mem0 / Hindsight  

**相对 YggForge**  
学习用；不替代真源与投影。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 6 | 6 | 4 | 2 | 6 |

---

### 5.8 Obsidian

**特点**  
闭源 PKM 应用 + 开放本地 Markdown vault；双链、图谱、插件生态。常作「人编辑、Agent 读写同一批 md」的壳。

**优点**

- 人类编辑与浏览体验极强  
- vault 即文件，易与 Git 真源共存  
- 插件生态覆盖预览、图谱、任务等  

**缺点**

- 不是记忆引擎，也不提供晋升门禁  
- 应用本身闭源；协作与 CI 仍靠 Git  
- 默认无 `ygg associate` 这类可审计联想 CLI  

**相对 YggForge**  
UI 壳：导出 / 同步 vault ↔ `knowledge/`；真源与投影仍以本仓为准。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 9 | 5 | 2 | 9 | 7 | 3 |

---

### 5.9 Memmy 类（跨工具偏好同步）

**特点**  
桌面 / 本地同步器：扫描多 AI 工具历史，把偏好、决策、上下文注入下一会话。解决「每个工具从零开始」。**不是** Mem0，也不是 Memary。

**优点**

- 跨工具冷启动体验好  
- 对个人偏好同步刚需直接  

**缺点**

- 几乎不做规范分层 / 晋升 / 可审联想  
- 历史扫描带来隐私与噪声面  
- 不能当工程制度仓  

**相对 YggForge**  
同步面互补；本仓 MCP 暴露后可部分替代「把制度送进各工具」的需求。

| 存储清晰可审 | 检索深度 | 自动化 | 轻量可维护 | 工程制度拟合 | 会话记忆拟合 |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 4 | 7 | 5 | 2 | 7 |

---

## 6. 主观对照表

维度说明（均为 **1–10 主观分**）：

| 维度 | 高分意味着 |
| --- | --- |
| 存储清晰可审 | 边界清楚、可 Git/可追溯、少糊成一团 |
| 检索深度 | 混合检索、图、时间、社区等能力强 |
| 自动化 | 少人工即可捕获 / 抽取 / 巩固 |
| 轻量可维护 | 依赖少、默认可本地、十年可搬迁 |
| 工程制度拟合 | 规范/错题/投影/门禁匹配度 |
| 会话记忆拟合 | 跨会话个性化与事实保持 |

| 项目 | 存储可审 | 检索 | 自动 | 轻量 | 工程制度 | 会话记忆 | 约均\* |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **YggForge** | 9 | 6 | 6 | 9 | **9** | 4 | **7.2** |
| GraphRAG | 3 | 9 | 9 | 2 | 3 | 4 | 5.0 |
| Hindsight | 4 | 9 | 10 | 3 | 3 | **9** | 6.3 |
| OpenViking | 5 | 8 | 8 | 4 | 4 | 7 | 6.0 |
| TencentDB-AM | 7 | 6 | 8 | 6 | 5 | 8 | 6.7 |
| Hyper-Extract | 6 | 6 | 9 | 6 | 4 | 3 | 5.7 |
| Mem0 | 4 | 8 | 8 | 6 | 3 | **9** | 6.3 |
| Memary | 4 | 6 | 6 | 4 | 2 | 6 | 4.7 |
| Obsidian | **9** | 5 | 2 | **9** | 7 | 3 | 5.8 |
| Memmy 类 | 3 | 4 | 7 | 5 | 2 | 7 | 4.7 |

\*简单算术平均，**未加权**，且**主观**。YggForge 在「工程制度」轴领先，在「会话记忆」轴故意不与 Hindsight/Mem0 抢主责——这是问题定义，不是跑输。

---

## 7. 组合建议

```text
人编辑 UI（可选）     Obsidian ↔ Git 真源（YggForge knowledge/）
Agent 投影             ygg deploy → ~/.*/yggforge-core
会话碎片（可选）       Mem0 / Hindsight
大语料问答（可选）     GraphRAG（边界：结果进 sources，不直接改 rules）
抽取（可选）           Hyper-Extract → sources/inbox → distill → promote
过程噪音（可选）       TencentDB 式 canvas → 仅 runtime
跨工具偏好（可选）     Memmy 类；或本仓未来 MCP
渐进加载 / RRF / 时间  见 opt-plan 待办，思想来自 OpenViking / Hindsight
```

过滤准则仍用 [../opt-plan/00-first-principles.md](../opt-plan/00-first-principles.md) 四问；借鉴清单见 [../opt-plan/02-borrow.md](../opt-plan/02-borrow.md)。

---

## 8. 相关文档

| 文档 | 用途 |
| --- | --- |
| [../opt-plan/00-first-principles.md](../opt-plan/00-first-principles.md) | 过滤准则 |
| [../opt-plan/01-comparison.md](../opt-plan/01-comparison.md) | 机制证据（借鉴用） |
| [../opt-plan/02-borrow.md](../opt-plan/02-borrow.md) | 借鉴 / 拒绝 |
| [../opt-plan/03-optimizations.md](../opt-plan/03-optimizations.md) | 本仓后续优化 |
| [../concepts/memory-and-association.md](../concepts/memory-and-association.md) | 本仓记忆与联想 |
| [canvases/](canvases/README.md) | Canvas 副本（可能过时） |

> 旧版 `oss-comparison.html` 浏览器预览已下线（以本文 Markdown 为唯一权威）。

若需更新 HTML/Canvas，请以**本文**为唯一权威重新导出。
