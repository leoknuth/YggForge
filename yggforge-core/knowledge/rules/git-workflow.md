---
id: 20260701165030-kr$$$$-gwfaa$$$-rjdq
title: Git Workflow For AI Agents
type: rule
status: active
confidence: high
source: agent-profile
scope: Agent-assisted repository operations
last_reviewed: 2026-07-27
owners:
  - team
tags:
  - git
  - workflow
  - agent
keywords:
  - git add
  - git commit
  - git push
  - git status
  - git fetch
  - pull --rebase
  - push safety
  - conflict
related:
  - 20260701165030-kr$$$$-mapw$$$$-ktcc
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及提交、推送、同步、状态判断、导入回仓库时优先加载
---
# Git Workflow For AI Agents

## 串行纪律

- `git add`
- `git commit`
- `git push`
- `git status`

这些步骤属于强依赖链路，必须串行执行，不要并行化。

## Push 前远端对齐（强制）

凡将执行 `git push`（含经 `ygg push` / Agent 直接调用），**必须先与远端对齐**，禁止在未知 `ahead/behind` 时直推。

### 目标效果（自己并入自己的提交）

期望的用户体验是：

1. 本地 `commit` 出自己的提交
2. 若远端有更新：用 **rebase** 把远端接到自己的提交链底下
3. **直接 `push`** 自己的提交

因此：

- **不生成合并提交**（不要 `git merge` / 不要 `pull` 默认 merge）
- **不走 Merge Request / 他人批准合并** 这一层仪式；对齐后由本人直推
- 唯一需要人工介入的是 **rebase 冲突**（内容冲突，不是“批准 merge”）

口语里的「自己 merge 自己」在本仓库 = **rebase + 直推**，不是 GitLab/GitHub 的 Merge Request。

### 术语（勿混用）

| 操作 | 含义 | 本仓库默认 |
| --- | --- | --- |
| `fetch` | 只更新远端引用，不改本地提交 | 对齐前必做 |
| `pull --rebase` | 取远端新提交，再把**本地未推送 commit 接到远端之上**（线性历史） | **默认策略** |
| `merge` / MR 合并 | 生成合并提交，或等别人点 Approve/Merge | **不用** |

### 标准步骤

1. `git fetch <remote>`（默认 `origin`）
2. 计算相对上游的 `ahead` / `behind`（`HEAD...@{u}` 或 `HEAD...<remote>/<branch>`）
3. 若 `behind > 0`：先向使用者发出「远端领先」提示，再执行 `git pull --rebase`（工作区 dirty 时加 `--autostash`）
4. 若 rebase **冲突**：立即停止，发出冲突警告，**等待人类决策**；不得擅自 `--abort` / `--skip` / 强推
5. 若已对齐或 rebase 成功且工作区干净：直接 `git push` 本地提交（线性历史）；`ygg push` 仍可附带风险摘要，但**不得**把“无法检查权限”当成必须批准才能推
6. 用 `git status -sb` 做内部核验后再回报

推荐入口：`ygg sync`（只对齐）/ `ygg push`（对齐 + 可选风险摘要 + 直推）。Agent 若直接调 git，须复现同一语义。

### 固定提示语（对使用者）

对齐与冲突相关的对话提示**必须**使用下列格式（可补一行仓库路径 / 分支名，但标题行保持不变）：

**远端领先（将 rebase 后直推）**

```text
[YggForge git] 远端领先
- 分支: <branch>（跟踪 <remote>/<branch>）
- 本地 ahead=<A>，behind=<B>
- 动作: pull --rebase 后直接 push（不生成合并提交）
```

**已与远端对齐**

```text
[YggForge git] 已与远端对齐
- 分支: <branch>
- 本地 ahead=<A>，behind=0
- 动作: 直接 push 本地提交（不生成合并提交）
```

**rebase 冲突（必须等人）**

```text
[YggForge git] rebase 冲突 — 已暂停，请人工决策
- 分支: <branch>
- 建议:
  1. 解决冲突后: git add ... && git rebase --continue
  2. 放弃本次对齐: git rebase --abort
- 在你确认前，不会继续 push
```

**push 完成**

```text
[YggForge git] push 完成
- 目标: <remote>/<branch>
- 本地 tip: <short-sha> <subject>
```

脚本侧（`ygg sync` / `ygg push`）机器可读行格式见 `docs/reference/sync.md`「对齐提示格式」；语义须与上表一致。

## 证据优先

- “无差异”“已提交”“已推送”这类结论必须基于实际命令结果
- 至少用 `git status --short` 或 `git status -sb` 做内部核验
- 不要仅凭预期或口头推断回报 git 状态
- “已与远端对齐 / 远端领先 / 有冲突”必须来自 `fetch` 后的 `ahead/behind` 或 rebase 退出码，不得臆测

## 回报约束

- 默认向用户回报高信息密度摘要，而不是整段原始命令输出
- 若发生 commit，优先回报：
  - 仓库路径
  - commit id
  - 提交标题
  - `git show --stat` 摘要
- 若发生 push 前对齐，优先用本节「固定提示语」，再附必要细节
- `git status` 默认用于内部校验，只有用户明确要求时再展示原始输出

## 提交信息

- 提交标题建议使用 `type(scope): 简要说明`
- 常用 `type` 可为：`feat`、`fix`、`docs`、`refactor`、`chore`
- 提交正文以中文为主，重点说明“为什么做”和“影响范围”

## 安全边界

- 不在提交信息中泄露密钥、密码、token、内网敏感地址
- 禁止 force push 到共享保护分支（除非用户在当次对话中明确要求并知情）
- 对 push 前的权限、保护分支、多人高权限风险检查，应集中在 `ygg push` / `git_risk_check` 入口处理，不要在多个规则里重复写实现细节
- rebase 冲突时只警告与停手，不代替用户做取舍

## Applies To

- Agent 辅助的仓库操作
- `ygg sync` / `ygg push` 与等价 git 直调

## Not For

- 具体业务代码逻辑
- 非本仓库的一次性实验分支策略（除非用户另行指定）
