# 同步文档

## 目录

- [1. 目标](#1-目标)
- [2. 三类同步](#2-三类同步)
  - [Repo Sync](#repo-sync)
  - [Projection Sync](#projection-sync)
  - [Reverse Sync / Import](#reverse-sync--import)
- [3. 为什么不再使用 Cursor 专属 sync](#3-为什么不再使用-cursor-专属-sync)
- [4. 策略文件](#4-策略文件)
- [5. `ygg sync` 与 `ygg push`](#5-ygg-sync-与-ygg-push)
- [6. 各部署模式下的语义](#6-各部署模式下的语义)
- [7. Push 风险检查](#7-push-风险检查)
- [8. Push 前远端对齐](#8-push-前远端对齐)
- [9. 对齐提示格式](#9-对齐提示格式)
- [10. 推荐工作流](#10-推荐工作流)

---

## 1. 目标

`YggForge` 的同步机制不再围绕某一个 Agent 的私有目录设计，而是围绕：

- 仓库真源
- 投影部署模式
- deploy manifest
- git 多机协作

来统一建模。

这意味着：

- Cursor、OpenCode、Codex 都使用同一套仓库级 sync 语义
- Agent 差异只保留在 `profiles/<agent>/` 和 deploy config 中
- 是否需要 import，不由某个 Agent 的目录规则决定，而由最近一次部署模式决定

## 2. 三类同步

### Repo Sync

仓库与远端 Git 的同步。

典型动作：

- `ygg sync`
- `ygg push`

对应实现：

- `yggforge-core/scripts/cmds/ops/git_sync.py`
- 推荐入口：`ygg sync` / `ygg push`（受 [behavior-config.md](behavior-config.md) 中 `git.*` 约束）

#### 多机协作要点

1. 开工前先 `ygg sync`（先 `fetch`，若远端领先再 `pull --rebase`；dirty 时带 autostash）  
2. 本地提交整理后再 `ygg push`（同样先对齐，冲突则停手等人）  
3. 单机不配远程时，把 `git.update` / `git.push` / `deploy.git_sync_after` 设为 `deny`  
4. 底层脚本一般不必直接调用：`yggforge-core/scripts/git_sync.{ps1,sh}`（根包装）与 `cmds/ops/git_sync.py`（实现）  
5. Agent 纪律真源：`yggforge-core/knowledge/rules/git-workflow.md`

### Projection Sync

把仓库中的投影入口部署到某个 Agent 的全局目录。

典型动作：

- `ygg deploy cursor`
- `ygg deploy codex`

对应实现：

- `yggforge-core/scripts/cmds/ops/deploy.py`
- `yggforge-core/config/deploy.defaults.json`

### Reverse Sync / Import

当部署模式不是 `link` 时，把 Agent 全局目录中的改动回收到仓库。

典型动作：

- `ygg import cursor`
- `ygg sync cursor`
- `ygg push cursor`

对应实现：

- `yggforge-core/scripts/cmds/ops/deploy.py --action import`
- `yggforge-generated/deploy-manifests/*.json`

## 3. 为什么不再使用 Cursor 专属 sync

旧的 `agent-profile` 把 sync 建模为：

- 监听 `~/.cursor/**` 的变更
- 再触发回收和 git 更新

这套设计只适合 Cursor。

`YggForge` 改为：

- 先看目标是哪个 Agent
- 再看最近一次 deploy manifest 中记录的模式
- 再按 `yggforge-core/config/sync.defaults.json` 决定是否在 `sync/push` 前执行 import

因此：

- `link`
  - 不需要 reverse sync
- `copy`
  - 需要 import 回 canonical source
- `render`
  - import 到 `yggforge-generated/imports/` 做 review

## 4. 策略文件

仓库级 sync 策略文件：

- `yggforge-core/config/sync.defaults.json`
- `yggforge-runtime/config/sync.local.json`
- `yggforge-core/config/sync.local.example.json`

其中：

- `sync.defaults.json`
  - 入库
  - 作为团队默认策略
- `sync.local.json`
  - 不入库
  - 作为本机覆盖层
- `sync.local.example.json`
  - 入库
  - 作为本机配置示例

当前默认策略是：

- `link`
  - `sync/push` 前不 import
- `copy`
  - `sync/push` 前自动 import
- `render`
  - `sync/push` 前自动 import
  - 但 import 目标仍由 deploy manifest 决定，默认进入 review 区而不是覆盖真源

另外还包含一组仓库级 push safety 策略：

- `gitlab.api_url`
- `gitlab.token_env`
- `push_safety.protected_branch_patterns`
- `push_safety.on_risky_protected_branch`
- `push_safety.on_unable_to_check_permissions`

## 5. `ygg sync` 与 `ygg push`

### 只做仓库 Git 同步

```powershell
pwsh -File .\ygg.ps1 sync
```

```bash
./ygg.sh sync
```

### 对指定 Agent 先做 reverse sync，再拉最新

```powershell
pwsh -File .\ygg.ps1 sync cursor
pwsh -File .\ygg.ps1 sync codex
```

```bash
./ygg.sh sync cursor
./ygg.sh sync codex
```

### 对指定 Agent 先做 reverse sync，再 update + push

```powershell
pwsh -File .\ygg.ps1 push cursor
```

```bash
./ygg.sh push cursor
```

语义是：

1. 如果目标存在 deploy manifest
2. 根据其中记录的最近部署模式判断是否需要 import
3. 完成 import 后，再进入仓库级 git sync 流程

`ygg push` 还会在真正 `git push` 前执行一次仓库级风险检查。

## 6. 各部署模式下的语义

### `link`

- 全局改动已经直接落在仓库
- `ygg sync <target>` 会跳过 import
- 只做 git update / push

### `copy`

- 全局改动发生在副本
- `ygg sync <target>` / `ygg push <target>` 会先 import
- import 目标是 canonical source

### `render`

- 全局改动发生在生成物副本
- `ygg sync <target>` / `ygg push <target>` 会先 import
- import 目标默认是 `yggforge-generated/imports/`
- 后续是否晋升回真源，需要人工 review

## 7. Push 风险检查

`YggForge` 已把旧 `agent-profile` 里的 push risk check 提升为仓库级工具：

- `yggforge-core/scripts/cmds/ops/git_risk_check.py`

执行时机：

- `ygg push`
- `yggforge-core/scripts/cmds/ops/git_sync.py --action update-push`

当前语义：

- 只对 `main` / `master` 这类受保护分支做风险判断
- 若能访问 GitLab API，就根据 protected branch 的 push 权限和成员列表判断是否属于“多人高权限直推风险”
- 若无法检查权限，则按 `push_safety.on_unable_to_check_permissions` 决定默认动作
- 若判断为高风险，则按 `push_safety.on_risky_protected_branch` 决定默认动作

默认策略（配合「自己提交、自己直推」）：

- 风险不可判定（未配 GitLab API / token）：`continue`（不拦截直推）
- 风险明确较高（多人高权限共推保护分支）：`ask_user`

本仓库默认工作流是 **线性历史直推**：`commit` → 必要时空 `pull --rebase` → `push`。  
不生成合并提交，也不把 push 做成“等人批准 Merge Request”。

若要启用真实的 GitLab 权限检查，建议：

1. 复制 `yggforge-core/config/sync.local.example.json` 为 `yggforge-runtime/config/sync.local.json`
2. 填入你的 `gitlab.api_url`
3. 在本机环境变量中设置 `YGG_GITLAB_TOKEN`

多人共享主分支且希望更保守时，可在 `sync.local.json` 把 `on_unable_to_check_permissions` 改回 `ask_user`。

## 8. Push 前远端对齐

`ygg sync` / `ygg push` 在改动本地提交历史或推送前，按下列顺序对齐远端（实现：`cmds/ops/git_sync.py`）：

1. `git fetch <remote>`
2. 计算 `ahead` / `behind`（相对 `@{u}` 或 `<remote>/<branch>`）
3. 若 `behind > 0`：打印远端领先提示，再 `git pull --rebase`（dirty 时 `--autostash`）
4. 若 `behind == 0`：打印已对齐，跳过 pull
5. 若 rebase 冲突：打印冲突警告并以非零退出，**不**继续 push
6. `ygg push` 在对齐成功且工作区干净后，再跑 push 风险检查，最后 `git push`

说明：

- 默认策略是 **rebase + 直推**：把本地未推送 commit 接到远端之上，再 push 自己的提交
- **不生成合并提交**；也不走 MR / 他人 Approve 才能进主线
- 口语「自己 merge 自己」= rebase 后直推，不是 Merge Request
- Agent 直接调用 `git push` 时，也应遵守同一语义（见 `git-workflow.md`）

## 9. 对齐提示格式

### 对使用者（对话 / 规则）

标题行保持固定，便于检索与习惯：

```text
[YggForge git] 远端领先
- 分支: <branch>（跟踪 <remote>/<branch>）
- 本地 ahead=<A>，behind=<B>
- 动作: pull --rebase 后直接 push（不生成合并提交）
```

```text
[YggForge git] 已与远端对齐
- 分支: <branch>
- 本地 ahead=<A>，behind=0
- 动作: 直接 push 本地提交（不生成合并提交）
```

```text
[YggForge git] rebase 冲突 — 已暂停，请人工决策
- 分支: <branch>
- 建议:
  1. 解决冲突后: git add ... && git rebase --continue
  2. 放弃本次对齐: git rebase --abort
- 在你确认前，不会继续 push
```

```text
[YggForge git] push 完成
- 目标: <remote>/<branch>
- 本地 tip: <short-sha> <subject>
```

### 脚本机器可读行（stdout）

| 键 | 含义 |
| --- | --- |
| `fetch` | `ok -> <remote>` |
| `align_check` | `ahead=N behind=M upstream=...` |
| `align_notice` | 远端领先 / 已对齐 / unknown 时的动作说明 |
| `update` | `ok -> pull --rebase`（或带 `--autostash`） |
| `push` | `ok -> <remote>/<branch>` |
| `push_tip` | 推送后 tip 的短 sha + subject |
| `push_note` | 是否在 push 前做过 rebase |

冲突时完整中文块写到 **stderr**，退出码非零。

## 10. 推荐工作流

推荐按下面的顺序工作：

1. `ygg sync`
2. 修改仓库真源，或修改某个 Agent 副本
3. 若改的是副本：
   - `ygg sync <target>`
   - 或 `ygg push <target>`
4. 提交后用 `ygg push`（或等价「先对齐再 push」）推送仓库

如果你的目标工具支持 `link`，优先使用 `link`。

这样：

- sync 语义最简单
- 不需要额外 reverse sync
- 多机一致性也最好
