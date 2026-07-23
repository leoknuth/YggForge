# 使用文档

## 目录

- [1. 日常使用方式](#1-日常使用方式)
- [2. 按部署模式工作的方式](#2-按部署模式工作的方式)
  - [`link`](#link)
  - [`copy`](#copy)
  - [`render`](#render)
- [2.1 平台入口](#21-平台入口)
- [2.2 import 安全机制](#22-import-安全机制)
- [3. 如何新增知识](#3-如何新增知识)
  - [新增团队规范](#新增团队规范)
  - [新增模板](#新增模板)
  - [新增经验 / 错题本](#新增经验-错题本)
  - [新增外部来源](#新增外部来源)
- [4. 知识条目建议字段](#4-知识条目建议字段)
- [5. 建议工作流](#5-建议工作流)
  - [人类主导](#人类主导)
  - [Agent 协助](#agent-协助)
- [6. 错题本机制](#6-错题本机制)
  - [6.1 Runtime Memory Backend](#61-runtime-memory-backend)
- [7. 何时升级为规则](#7-何时升级为规则)

---

## 1. 日常使用方式

这个仓库的典型使用方式不是“让 Agent 每次读完整仓库”，而是：

1. Agent 先读取部署入口
2. 入口告诉它优先关注哪些规则和索引
3. 面对用户问题时，按[综合回答策略](../reference/triggers.md#综合回答策略三源综合)综合三源：
   - **模型推理** — 先形成初步判断
   - **ygg 检索** — `ygg associate`（seed tags）或 `ygg recall`；Cursor 部署下由钩子 `last_trigger.json` 的 `action` 路由
   - **联网搜索** — 事实类、时效敏感类问题必须 WebSearch
4. 综合作答并标注来源/置信度；不得仅凭 ygg 命中条目作答
5. 命中后再读取少量模板或经验文件精读

## 2. 按部署模式工作的方式

### `link`

这是默认工作方式。

- 全局生效文件直接链接到仓库
- Agent 的改动天然已经进入仓库
- 日常同步只需要 git
- Windows 和 Linux 都应优先采用该模式
- 如果你不确定 `link` 和 `render` 的区别，先看 [部署文档](deploy.md) 里的详细解释和例子

如果仓库在多台机器上共同维护，建议不要直接裸 `git pull / push`，而是使用：

- `ygg sync` / `ygg push`（推荐）
- 兼容旧入口：`git_sync.ps1|.sh`（无参→sync；含 push→push；或旧 `--action update`）

具体见：

- [同步文档](../reference/sync.md)（含多机 git）
- [ygg 统一入口](../reference/ygg-cli.md)

### `copy`

这是兼容模式。

- 部署后全局位置是副本
- 如果改动发生在副本里，需要显式 `import`
- 也可以直接使用 `ygg sync <target>` 或 `ygg push <target>`
- 这两个命令会先按最近 deploy manifest 决定是否 import，再做仓库级 git 同步
- 不建议长期作为主模式

### `render`

- 适合需要生成专用入口文件的工具
- 渲染产物不算知识真源
- 生成物统一进入 `yggforge-generated/`
- 当前 render 产物会进入 `yggforge-generated/rendered/`
- render 模式下的 import 会进入 `yggforge-generated/imports/`，用于人工复核
- 它和 `link` 的核心区别是：`link` 解决“目标指向谁”，`render` 解决“目标内容长什么样”
- `ygg sync <target>` / `ygg push <target>` 在 render 模式下会先导入 review 区，再继续 git 流程

## 2.1 平台入口

Windows:

```powershell
.\ygg.ps1 status
```

Linux:

```bash
./ygg.sh status
```

## 2.2 import 安全机制

`import` 现在会先做预览，再决定是否写入：

- 若最近一次模式是 `link`
  - 直接 `no-op`
- 若目标与导入目的地内容相同
  - 直接 `no-op`
- 若是文本文件
  - 默认输出统一 diff 预览
- 若是 `render`
  - 默认导入到 `yggforge-generated/imports/`

只预览不导入：

```bash
./ygg.sh import cursor
# 仅预览不写回时，可用兼容旧旗标：
./yggforge-core/scripts/deploy.sh --action import --targets cursor --preview-only
```

## 3. 如何新增知识

### 新增团队规范

把高稳定、需要反复遵守的内容放到：

- `knowledge/rules/`

### 新增模板

把可直接复用的代码骨架放到：

- `knowledge/templates/`

### 新增经验 / 错题本

把踩坑、反例、事故复盘、性能结论放到：

- `knowledge/lessons/`

如果要快速把一条用户纠正或可复用偏好沉淀成草稿，可以直接使用：

```bash
./ygg.sh remember 以后说明路径时先给绝对路径再解释
```

它会把草稿写到：

- `yggforge-runtime/memory/raw/`
- `knowledge/lessons/inbox/`

如果标题或内容与已有草稿/经验重复，`remember` 默认会直接返回现有条目而不是重复写入。

### 新增外部来源

先把来源材料放到：

- `knowledge/sources/inbox/`

提炼之后再进入：

- `knowledge/sources/distilled/`

## 4. 知识条目建议字段

建议每个条目都尽量回答以下问题：

- 这是什么结论
- 适用于什么场景
- 不适用于什么场景
- 来源是什么
- 最后一次审核是什么时候
- 是否已经进入强规范

## 5. 建议工作流

### 人类主导

- 人类新增规则和模板
- Agent 帮忙改写、归档、建立索引

### Agent 协助

- Agent 总结博文和文档
- Agent 检查是否和既有规则冲突
- Agent 生成初稿
- 人类审核后晋升

## 6. 错题本机制

推荐把以下内容沉淀为错题：

- review 中反复出现的问题
- benchmark 退化的共性原因
- 并发与内存序误用
- ABI / 对齐 / 缓存行为误判
- 量化回测中的数据污染与前视偏差

对于 Agent 协作中的原则性纠正，优先使用仓库级流程：

- `ygg dream --scan`
- `ygg remember <note>`
- `ygg recall <query> [--type|--tag|--scope|--agent]`
- `ygg associate --tag <seed> [--hop N]`
- `ygg graph build`
- `ygg index`

而不是再写回某个 Agent 的私有记忆目录。

其中：

- `dream`
  - 扫描运行时记忆层和 lesson 草稿层
  - 找重复候选与待晋升候选
  - 可写出报告到 `yggforge-runtime/memory/index/`
- `remember`
  - 先写运行时 observation 到 `yggforge-runtime/memory/raw/`
  - 再镜像出一份 lesson 草稿到 `knowledge/lessons/inbox/`
- `recall`
  - 检索正式知识层、运行时 observation、lesson 草稿
  - 支持 `--type`（按条目 type）/ `--tag` / `--scope` / `--agent` 显式过滤
  - 与 `associate` 互补：偏 metadata / 正文打分
- `associate`
  - 从 seed tags 多跳联想，再收集条目与 related
  - 约定见 [retrieval-conventions.md](../concepts/retrieval-conventions.md)
- `graph build`
  - 重建 `graph/` 有序分片（默认不导出 by-tag）
- `index`
  - 扫描正式知识条目的 `tags`
  - 可选导出 `indexes/by-tag/`（含 EXPORT_META）

## 6.1 Runtime Memory Backend

`YggForge` 把运行时记忆层和 canonical knowledge 层分开。

- canonical knowledge
  - `knowledge/rules/`
  - `knowledge/templates/`
  - `knowledge/lessons/`
- runtime memory
  - `yggforge-runtime/memory/raw/`
  - `yggforge-runtime/memory/index/`
  - `knowledge/lessons/inbox/`

运行时记忆 backend 的规划如下：

| backend | 存储位置 | 数据结构 | 检索方式 | 适合的 YggForge 子命令 | 推荐优先级 |
| --- | --- | --- | --- | --- | --- |
| `file` | `yggforge-runtime/memory/raw/`、`yggforge-runtime/memory/index/`、`knowledge/lessons/inbox/` | Markdown / 文本文件 | 文件遍历 + 文本匹配 | `remember`、`recall`、`dream`、`promote` | **当前默认** |
| `sqlite` | 例如 `yggforge-runtime/memory/runtime.db` | observations / event / index / candidate 表 | SQL + 索引 + 时间过滤 | `recall`、`dream` | 未来第一优先 |
| `vector` | 本地向量索引目录或向量库存储 | embedding + metadata + text chunk | 语义检索 / hybrid search | `recall`、`dream` 候选召回 | 未来按需 |
| `mcp` | 外部 MCP memory service | 由外部服务定义 | 通过 MCP tools 查询 | `recall`、`dream`、外部集成 | 未来按需 |

当前项目**暂时只使用 `file` backend**。

其他 backend 的设计已经在文档中明确，但目前不作为实现承诺。

如果你想进一步理解 file backend 下的“智能加载”约定，见：

- [retrieval-conventions.md](../concepts/retrieval-conventions.md)

## 7. 何时升级为规则

只有在以下条件同时满足时，才建议从 lesson 升级到 rule：

- 已多次复现
- 代价足够高
- 适用边界明确
- 团队达成一致

最小晋升闭环已经支持：

```bash
./ygg.sh promote <inbox-entry> rule --dry-run
./ygg.sh promote <inbox-entry> lesson
./ygg.sh promote <inbox-entry> template
```

当前版本会：

- 从 `knowledge/lessons/inbox/` 读取草稿
- 写入目标目录
- 更新最小 front matter 字段（含 `type`、`status`、`id`、`last_reviewed`）
- 自动更新目标目录下 README 的“当前条目”列表
- 删除原 inbox 草稿

当前版本不会：

- 自动维护所有 README 索引
- 自动重写复杂元数据
- 自动做跨文件引用修复

批量晋升也已经支持：

```bash
./ygg.sh promote rule --all --dry-run
```
