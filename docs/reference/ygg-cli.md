# ygg 统一入口

## 目录

- [1. 目标](#1-目标)
- [2. 入口文件](#2-入口文件)
- [3. 显式动作](#3-显式动作)
- [4. 示例](#4-示例)
- [5. 自然语言路由](#5-自然语言路由)
- [6. 当前限制](#6-当前限制)

---

## 1. 目标

`ygg` 是 `YggForge` 的统一入口。

它支持两种用法：

- 显式动作
  - `ygg status`
  - `ygg ingest`
- 通用意图
  - `ygg 把这篇文章收进知识库`
  - `ygg 部署到 cursor`

## 2. 入口文件

- 仓库根 `ygg.sh` / `ygg.ps1`
  - 推荐日常入口（转发到核心包）
- `yggforge-core/scripts/ygg.py`
  - 跨平台核心
- `yggforge-core/scripts/ygg.ps1`
  - Windows / PowerShell 包装器
- `yggforge-core/scripts/ygg.sh`
  - Linux / Bash 包装器

## 3. 显式动作

当前第一版支持：

- `status`
- `deploy`
- `import`
- `sync`
- `push`
- `ingest`
- `distill`
- `dream`
- `recall`
- `remember`
- `promote`
- `index`
- `graph`
- `associate`
- `tag`
- `behavior`
- `doctor`

其中已自动化打通的包括上述全部显式动作（含 `graph` / `associate` / `tag` / `behavior` / `doctor`）。

`behavior` 查看当前生效的 ask/allow/deny 等策略（见 [behavior-config.md](behavior-config.md)）。
`doctor` 一站式健康检查：Python / git / 布局 / 配置 / catalog / MDC 投影 / 重复 id / **plugins 注册表** / **deploy targets** / hooks / trigger / **tag-graph 一致性** / **BOM**；输出红/黄/绿。按 `yggforge-core/scripts/requirements.txt` 自动检测依赖。补装缺失依赖：

- `ygg doctor --fix-deps`：检测并 pip install 缺失项（经 behavior 门禁 `deps.install`，默认 ask）
- `ygg doctor --fix-deps --yes`：非交互直接补装（CI 友好）

`deploy` 支持 `--scope user|project`：

- `--scope user`（默认）：整包核心 + 薄入口部署到 `~/.<agent>/`（一次性、跨项目共享）
- `--scope project`：只把薄入口投影到当前项目仓库（`<repo>/.cursor/rules/`、`<repo>/AGENTS.md` 等），让 Agent 原生自动加载；不部署整包；`--project-root <path>` 可指定项目根
- `--backup`：覆盖前把旧目标备份到 `yggforge-runtime/deploy-backups/<ts>/`
- `--install-deps`：部署前自动检测并补装缺失依赖（经 behavior 门禁 `deps.install`）

## 4. 示例

Windows:

```powershell
pwsh -File .\ygg.ps1 status codex
pwsh -File .\ygg.ps1 deploy link cursor
pwsh -File .\ygg.ps1 sync
pwsh -File .\ygg.ps1 sync cursor
pwsh -File .\ygg.ps1 push cursor
pwsh -File .\ygg.ps1 dream --scan
pwsh -File .\ygg.ps1 recall 路径 表达
pwsh -File .\ygg.ps1 remember 用户要求以后路径说明先写绝对路径再解释
pwsh -File .\ygg.ps1 promote 20260707-path-note.md rule --dry-run
pwsh -File .\ygg.ps1 ingest "https://mp.weixin.qq.com/s/..."
pwsh -File .\ygg.ps1 graph build
pwsh -File .\ygg.ps1 associate --tag simu --hop 2
pwsh -File .\ygg.ps1 associate --tag ygg --type skill --json
pwsh -File .\ygg.ps1 deploy link --scope project cursor
```

Linux:

```bash
./ygg.sh status codex
./ygg.sh deploy link cursor
./ygg.sh deploy link --scope project cursor
./ygg.sh sync
./ygg.sh sync cursor
./ygg.sh push cursor
./ygg.sh dream --scan
./ygg.sh recall 路径 表达
./ygg.sh remember 用户要求以后路径说明先写绝对路径再解释
./ygg.sh promote 20260707-path-note.md rule --dry-run
./ygg.sh ingest "https://mp.weixin.qq.com/s/..."
./ygg.sh graph build
./ygg.sh associate --tag simu --hop 2
./ygg.sh associate --tag git --tag workflow --json
./ygg.sh associate --tag ygg --type skill --json
```

`sync` 和 `push` 的新语义是：

- 不带 target
  - 只做仓库级 git 同步
- 带 target
  - 先根据最近 deploy manifest 和 `yggforge-core/config/sync.defaults.json` 判断是否 import
  - 再执行仓库级 git sync

`push` 额外包含一层仓库级 push safety 检查：

- 入口：`yggforge-core/scripts/cmds/ops/git_risk_check.py`
- 默认只针对 `main` / `master`
- 若风险不可判定或判定为多人高权限直推，默认动作是 `ask_user`

`dream` 的当前语义是：

- 扫描 `yggforge-runtime/memory/raw/`、`knowledge/lessons/inbox/`、`knowledge/lessons/`
- 找出重复候选和待晋升候选
- `--scan` 只读输出
- 不带 `--scan` 时会把报告写到 `yggforge-runtime/memory/index/`
- 当前默认只基于 `file` backend 工作

`recall` 的当前语义是：

- 检索运行时记忆层 `yggforge-runtime/memory/raw/`
- 同时检索正式知识：`rules/`、`templates/`、`decisions/`、`lessons/`（含草稿）、`sources/distilled/`
- 支持 `--type` / `--tag` / `--scope` / `--agent` 显式过滤（`--type` 按条目 **type** 过滤）
- 默认使用 `yggforge-core/config/memory.defaults.json` 里的 `file` backend

`associate` 的当前语义是：

- 从 seed tags 出发，按 `graph/tag-graph.yaml` 做多跳 tag 扩展
- 用 tag 反查表（tag→条目 id 倒排索引）取并集得到条目，再并上条目 `related`（默认 1 跳）
- 支持 `--type` 按 type 过滤命中（可重复，如 `--type skill` / `--type mcp-server` / `--type hook`，便于联想发现 `plugins/` 下的内部插件）
- 输出可阅读的相对路径列表
- 详见 [retrieval-conventions.md](../concepts/retrieval-conventions.md)、[../yggforge-core/graph/README.md](../../yggforge-core/graph/README.md)

`graph` 的当前语义是：

- `ygg graph build`：重建 catalog / tag-inverted 有序分片（默认不导出 by-tag）；扫描时校验 front matter schema v2（必填含 `type`）
- `ygg graph check`：校验警告（缺 id/`type`、死 related、路径过深、schema 等）
- `ygg project mdc`：将 `always_apply: true` 的 `knowledge/rules/*.md` 投影为 `profiles/cursor/rules/*.mdc`（`--check` 只检查）

`remember` 的当前语义是：

- 把一条用户纠正、偏好或经验先记录到运行时记忆层
- 再镜像出一份 `knowledge/lessons/inbox/` 下的草稿
- 默认来源是 `user`
- 默认范围是 `cross-project`
- 可以通过 `--title`、`--title-refined`、`--source`、`--scope`、`--tags` 覆盖/补充字段
- `title` 为原始标题；`title_refined` 为优化版标题（可选，不覆盖 title）
- `--tags` 由 LLM/调用方提供，经 `yggforge-core/graph/tag-synonyms.yaml` 归并后写入，并可更新 tag-graph
- 多数记忆类命令支持 `--json`
- 默认会做重复检测；若确实要重复落盘，可加 `--allow-duplicate`
- `--as rule` / `--standing`（或正文命中「以后一直这样」等）：写入 inbox 后自动 `promote --to rule --standing`

`tag` 的当前语义是：

- `ygg tag --list`：列出邻接图标签
- `ygg tag --add T1 T2`：添加标签节点
- `ygg tag --relate A B`：双向关联（可用 `--weight`）
- `ygg tag --suggest`：PPMI 共现建议边 → `yggforge-generated/indexes/tag-suggestions.json`
- `ygg tag --suggest --apply`：经 `tag_suggest_apply` 闸门合并进权威图
- `ygg tag --propagate T`：审查报告（不自动改文件）

当前 memory backend 策略：

| backend | 存储位置 | 数据结构 | 检索方式 | 适合的 YggForge 子命令 | 推荐优先级 |
| --- | --- | --- | --- | --- | --- |
| `file` | `yggforge-runtime/memory/raw/`、`yggforge-runtime/memory/index/`、`knowledge/lessons/inbox/` | Markdown / 文本文件 | 文件遍历 + 文本匹配 | `remember`、`recall`、`dream`、`promote` | **当前默认** |
| `sqlite` | 例如 `yggforge-runtime/memory/runtime.db` | 结构化表 | SQL + 索引 | `recall`、`dream` | 未来第一优先 |
| `vector` | 本地向量索引目录 | embedding + metadata | 语义检索 / hybrid search | `recall`、`dream` | 未来按需 |
| `mcp` | 外部 MCP memory service | 由外部服务定义 | MCP tool 调用 | `recall`、`dream`、外部集成 | 未来按需 |

当前项目只实现 `file` backend；其余 backend 仅为未来预留方案。

`promote` 的当前语义是：

- 输入来自 `knowledge/lessons/inbox/` 的一条草稿
- 也支持 `--all` 批量处理 inbox 草稿
- 目标可以是 `reference`、`lesson`、`rule`、`template` 或 `decision`
- 会把目标文件写到对应目录，并把 front matter 的 `status` 更新为 `active`（`decision` 默认 `accepted`），写入对应 **`type`**
- 若晋升到 `rule` / `lesson` / `reference` / `template` / `decision`，会按约定算法生成 `id`，并更新 `last_reviewed`
- 若晋升到 `template`，会补 `template_kind` 和 `last_reviewed`
- 会自动维护目标目录 README 中的“当前条目”列表
- `--auto --to reference --objective`：客观知识自动晋升路径
  - 走 `promote.auto_to_reference` 门禁（默认 `allow`）
  - `--objective` 在 front matter 写入 `objective: true` 留痕
  - 脚本自动跑标签联想查重（hop=0）：有雷同则标记 `duplicate_candidate` 并跳过
  - `--auto --to rule`（无 `--standing`）走 `promote.auto_to_rule`（默认 `deny`）
  - `--auto --to rule --standing` / `remember --as rule` 走 `promote.auto_to_rule_on_standing`（默认 `allow`）

更详细说明见：

- [同步文档](sync.md)（含多机 git）
- [部署文档](../guide/deploy.md)
- [检索约定](../concepts/retrieval-conventions.md)
- [知识图说明](../../yggforge-core/graph/README.md)

## 5. 自然语言路由

当前第一版会对以下意图做保守路由：

- 包含“部署 / deploy”
  - 路由到 `deploy`
- 包含“状态 / status / 怎么部署”
  - 路由到 `status`
- 包含“导入 / 导回”
  - 路由到 `import`
- 包含“同步 / 拉最新”
  - 路由到 `sync`
- 包含“推上去 / push”
  - 路由到 `push`
- 包含 URL 或“收进知识库 / 归档 / 入库”
  - 路由到 `ingest`
- 包含“提炼”
  - 路由到 `distill`
- 包含“做梦 / dream / 整理记忆”
  - 路由到 `dream`
- 包含“回忆 / recall / 搜索记忆”
  - 路由到 `recall`
- 包含“错题本 / 记住”
  - 路由到 `remember`
- 包含“升级成规则 / 晋升”
  - 路由到 `promote`
- 包含“索引”
  - 路由到 `index`
- 包含“建图 / graph build / 重建知识图”
  - 路由到 `graph build`
- 包含“联想 / associate / 关联检索”
  - 路由到 `associate`

## 6. 当前限制

- 自然语言路由是第一版，只覆盖高频意图
- 若意图过于模糊，`ygg` 会直接报错，而不是瞎猜
- `ygg graph build` 重建机器分片索引；`ygg index` 可选导出人类 by-tag（含时间/commit 元数据）；详见 [retrieval-conventions.md](../concepts/retrieval-conventions.md)
