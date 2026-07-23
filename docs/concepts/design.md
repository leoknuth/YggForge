# 设计文档

## 目录

- [0. 命名含义](#0-命名含义)
- [0.1 生成物目录](#01-生成物目录)
- [0.2 跨平台部署原则](#02-跨平台部署原则)
- [1. 目标](#1-目标)
- [2. 总体架构](#2-总体架构)
  - [2.1 规范层](#21-规范层)
  - [2.2 模板层](#22-模板层)
  - [2.3 经验层](#23-经验层)
  - [2.4 投影层](#24-投影层)
- [3. 为什么不用一个超大 AGENTS.md](#3-为什么不用一个超大-agentsmd)
- [4. 推荐目录模型](#4-推荐目录模型)
- [5. 单仓库、多投影](#5-单仓库-多投影)
- [6. 知识演化模型](#6-知识演化模型)
- [7. 检索策略](#7-检索策略)
- [8. 对不同 Agent 的兼容理解](#8-对不同-agent-的兼容理解)
- [9. 能力边界建议](#9-能力边界建议)

---

## 0. 命名含义

项目名为 `YggForge`。

- `Ygg`
  - 来自 `Yggdrasil`
  - `Yggdrasil` 常被中文意译为“世界树”
  - 这里借用的是“连接多界的根系结构”这一层意象
- `Forge`
  - 表示把原材料锻造成稳定、可复用、可部署的工程资产

因此，`YggForge` 不是一个被动的资料仓库，而是：

- 作为多 Agent 的共同根系
- 把知识、规范、模板、经验锻造成可执行资产
- 用统一真源向不同工具投影

> 命名背后的神话典故、锻造工序的隐喻，以及"为什么这么取名"的完整阐述，见 [philosophy.md](philosophy.md) §1。

## 0.1 生成物目录

本仓库统一使用 `yggforge-generated/` 存放这些内容：

- 部署清单
- 渲染产物
- 导入中间产物
- 非真源的本地状态
- 不应直接进入知识真源的机器相关文件

这个目录不是 canonical knowledge 的一部分。

## 0.2 跨平台部署原则

`YggForge` 的部署不应依赖某一个 shell。

因此推荐结构是：

- 用一个跨平台核心表达部署语义
- Windows 和 Linux 只保留很薄的入口包装
- 配置、清单、导入语义保持一致

当前实现采用：

- `yggforge-core/scripts/cmds/ops/deploy.py` 作为跨平台核心
- 仓库根 `ygg.ps1` / `ygg.sh` 作为统一 CLI 入口
- `yggforge-core/scripts/deploy.ps1|.sh` 作为兼容薄包装（转发到 `ygg` 或旧旗标直调 `cmds/ops/deploy.py`）
## 1. 目标

这个仓库是一个“单仓库、多投影”的 AI Agent 知识系统。

它要同时满足：

- 团队规范可沉淀
- 模板可复用
- 经验可检索
- 错题可回收
- 多 Agent 可兼容
- token 成本可控

## 2. 总体架构

建议把系统拆成四层。

### 2.1 规范层

用于保存高稳定、强约束内容：

- C++ 代码风格
- 量化研究流程约束
- 性能测试门槛
- review 清单
- 禁止事项

特点：

- 文件少
- 内容短
- 变更谨慎
- 适合直接投影到 Agent 入口配置

### 2.2 模板层

用于保存可直接复用的骨架和范式：

- CMake/Bazel 工程骨架
- benchmark 模板
- lock-free / low-latency 组件样板
- 回测与撮合模块骨架
- profiling 与 tracing 基线

特点：

- 更贴近代码
- 高复用
- 适合被 Agent 检索后直接改造

### 2.3 经验层

用于保存：

- 错题本
- 踩坑记录
- 事故复盘
- 性能调优案例
- 设计决策记录

特点：

- 强依赖上下文
- 必须写清适用边界
- 需要时间维度和来源信息

### 2.4 投影层

面向不同工具做适配：

- Cursor
- OpenCode
- Codex

投影层的职责只有两件事：

- 给工具提供它能识别的入口文件或目录
- 把真源映射出去，而不是复制出多份独立内容

## 3. 为什么不用一个超大 AGENTS.md

因为那会导致三个问题：

- Agent 每次都读太多，token 浪费明显
- 知识密度下降，检索命中率变差
- 规范、经验、草稿混在一起后很难维护

因此推荐：

- 用短入口文件做路由
- 用结构化目录做知识分层
- 用索引文件和元数据做定向检索

## 4. 推荐目录模型

```text
YggForge/                    # REPO_ROOT
  docs/
  ygg.sh / ygg.ps1
  yggforge-core/             # CORE_ROOT（可部署核心包）
    knowledge/
      rules/
      templates/
      lessons/
      decisions/
      sources/
        inbox/
        distilled/
    profiles/
      common/
      cursor/
      opencode/
      codex/
    scripts/
    schemas/
    graph/                   # tag-graph.yaml + 机器索引 catalog/tag-inverted
    config/
  yggforge-generated/        # 可再生产物（rendered/imports/manifests/indexes/scratch）
  yggforge-runtime/          # 本机记忆与 *.local.json
```

完整说明与关系图见 [layout.md](layout.md)。入口页：

- [../yggforge-core/knowledge/README.md](../../yggforge-core/knowledge/README.md)
- [../yggforge-core/profiles/README.md](../../yggforge-core/profiles/README.md)
- [../yggforge-core/scripts/README.md](../../yggforge-core/scripts/README.md)
- [../yggforge-runtime/README.md](../../yggforge-runtime/README.md)
- [../yggforge-generated/README.md](../../yggforge-generated/README.md)

## 5. 单仓库、多投影

这是本项目最重要的设计点。

仓库本身保存 canonical source。部署时再根据目标 Agent 生成它需要的投影。

推荐有三种部署模式：

- `link`
  - 用符号链接或 junction 将目标位置指向仓库内容
  - 默认模式
  - 最适合当前需求
- `copy`
  - 为不支持链接或行为不稳定的工具保留的兼容模式
- `render`
  - 从结构化条目渲染出工具专用入口文件

同步语义不是对称的：

- `link` 模式下，Agent 对目标文件的修改天然已经落在仓库里
- `copy` 模式下，若 Agent 修改的是全局副本，则需要显式导入回仓库
- `render` 模式下，渲染结果属于生成物，应进入 `yggforge-generated/`

## 6. 知识演化模型

推荐流程：

1. 投喂原始材料到 `knowledge/sources/inbox/`（或 `ygg remember` 写入运行时记忆 + lesson 草稿）
2. AI 提炼摘要、原则、反例、适用场景（`distill` / `dream`）
3. 生成到 `knowledge/sources/distilled/` 或 `knowledge/lessons/inbox/`
4. 晋升到多层资产（自动推进 / 人工审核）：
   - **逻辑**：`knowledge/rules/`（人工审核）
   - **技能 / SOP**：`knowledge/templates/`、`profiles/common/behavior-packs/`（人工审核）
   - **知识**：`knowledge/lessons/`、`knowledge/decisions/`、正式 sources（lessons 客观知识可设自动；decisions 人工写入）

这里的关键是：**系统可以持续自动迭代草稿与索引，但人要决定是否把草稿晋升为强规范。**

与「人类式联想」的衔接：晋升后的条目应补齐 `tags` / `related`，并由 `ygg graph build` 进入联想索引，使下次任务能按相关概念扩跳，而不是只靠关键词命中。

相关入口：

- [../yggforge-core/knowledge/sources/README.md](../../yggforge-core/knowledge/sources/README.md)
- [../yggforge-core/knowledge/lessons/README.md](../../yggforge-core/knowledge/lessons/README.md)
- [../yggforge-core/knowledge/templates/README.md](../../yggforge-core/knowledge/templates/README.md)
- [../yggforge-core/knowledge/rules/README.md](../../yggforge-core/knowledge/rules/README.md)
- [retrieval-conventions.md](retrieval-conventions.md)
- [../yggforge-core/graph/README.md](../../yggforge-core/graph/README.md)

## 7. 检索策略

为了避免每次读取整个仓库，采用「入口路由 → 三源综合 → 结构联想 / 文本召回 → 少量精读」：

1. 先读 profile 入口与图索引（`AGENTS.md`、`yggforge-core/graph/`；可选再看 `yggforge-generated/indexes/`）
2. **模型推理**形成初步判断；**联网搜索**验证事实/时效类问题（见 `knowledge/rules/standing-preference.md`）
3. 再按 seed tags 做 `ygg associate`（多跳 tag + 条目 related），或用 `ygg recall` 做 metadata/正文打分——前者模拟**人类式联想记忆**
4. 综合三源后只加载少量目标条目正文，标注来源与置信度

已实现：

- 关键词 / metadata `recall`
- tag 邻接图 `associate`
- 有序分片 catalog / tag-inverted（`ygg graph build`）

未来可按需加入：

- 向量检索
- hybrid retrieval
- 更细的语言 / 平台 / 时效性过滤

当前约定见：

- [retrieval-conventions.md](retrieval-conventions.md)
- [../yggforge-core/graph/README.md](../../yggforge-core/graph/README.md)
- [usage.md](../guide/usage.md)
- [ygg-cli.md](../reference/ygg-cli.md)

## 8. 对不同 Agent 的兼容理解

要兼容的不是“同一份文件内容”，而是“同一份知识真源”。

因此：

- 仓库内部保持通用格式
- 对外适配各 Agent 的入口习惯
- 通过脚本和配置描述映射关系

## 9. 能力边界建议

不要一上来追求全自动复杂 RAG。本仓默认路径是：

1. 仓库结构、规则分层、模板基线  
2. 部署脚本与多 Agent 投影  
3. 摄取 / 提炼 / 记忆闭环（`remember` → `promote`）  
4. tag 图联想与有序分片索引（`graph` / `associate`）  

更重的检索与自动化见 [../opt-plan/README.md](../opt-plan/README.md)。
