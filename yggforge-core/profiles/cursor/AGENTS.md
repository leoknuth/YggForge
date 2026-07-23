# Cursor 投影入口

你正在使用一个由仓库驱动的工程知识系统。

已部署时，核心包位于 `~/.cursor/yggforge-core/`（链接到仓库 `yggforge-core/`）。
下文路径均相对该核心包根目录（与仓库内 `yggforge-core/` 相对路径一致）。

## 目录

- [优先级](#优先级)
- [推荐入口](#推荐入口)
- [同步约束](#同步约束)
- [记忆约束](#记忆约束)
- [MCP 与密钥](#mcp-与密钥)
- [知识联想检索与综合回答](#知识联想检索与综合回答)

## 优先级

1. 先遵守当前文件中的投影约束
2. 先吸收 `profiles/common/behavior-packs/karpathy-guidelines.md`
3. 优先读取 `knowledge/rules/` 中的规范
4. 在 `knowledge/templates/` 中查找可复用实现模式
5. 在 `knowledge/lessons/` 中查找踩坑和反例

不要默认扫描整个仓库。

先用通用行为包约束做事方式，再用知识规则约束做事内容。

## 推荐入口

- `profiles/common/behavior-packs/karpathy-guidelines.md`
- `knowledge/rules/agent-coding-discipline.md`
- `knowledge/rules/compatibility-defaults.md`
- `knowledge/rules/workspace-format.md`
- `knowledge/rules/secrets-placeholder-boundary.md`
- `knowledge/rules/cpp-style.md`
- `knowledge/rules/python-style.md`
- `knowledge/rules/markdown-docs.md`
- `knowledge/rules/performance-checklist.md`
- `knowledge/rules/standing-preference.md`
- `knowledge/templates/README.md`
- `knowledge/lessons/README.md`

本 profile 把强制检索钩子投影到 **用户级** `~/.cursor/hooks/` + `~/.cursor/hooks.json`（见 `profiles/cursor/hooks/`），由 `ygg deploy link cursor` 安装。回答任何用户消息前：先 Read `yggforge-runtime/cache/last_trigger.json`（或部署后的等价路径），再按 `action` 路由。

薄规则文件真源在核心包内 `profiles/cursor/rules/`（含 `ygg-default-trigger.mdc` 与 `ygg-answer-synthesis.mdc`）。**全局部署不再投影到 `~/.cursor/rules/`**——Cursor 原生不自动加载该目录（官方 Project Rules 仅认项目内 `.cursor/rules/`；User Rules 在 Settings 纯文本）。会话开始时主动 Read 核心包内上述两个 `.mdc`（或 `knowledge/rules/default-trigger-routing.md` 与 `standing-preference.md` 真源）。若要让 Cursor 原生自动加载薄规则，用项目级部署 `ygg deploy --scope project` 把它们投影到 `<repo>/.cursor/rules/*.mdc`。

## 同步约束

- 先看最近部署模式，再决定是否需要 reverse sync
- 若当前目标通过 `link` 部署，改动已直接落在仓库，不需要额外 import
- 若当前目标通过 `copy` 或 `render` 部署，优先使用 `ygg import cursor`、`ygg sync cursor` 或 `ygg push cursor`
- 不要把 Cursor 私有路径约束写成知识真源规则
- 不要使用已废弃的「改 `~/.cursor` → 自动回收到工程仓库」闭环

## 记忆约束

- 用户要求「记住」「写进错题本」时，优先使用 `ygg remember ...`
- 用户说「以后一直这样」「写成规则」「升级成 rules」等**站立偏好**时，使用 `ygg remember "..." --as rule`（正文命中站立句式也会自动等价）；脚本会写入 inbox 后自动 `promote --to rule --standing`
- 记忆先进入仓库级 `knowledge/lessons/inbox/`，而不是 Cursor 私有目录
- 普通草稿足够稳定时，使用 `ygg promote <entry> lesson|rule|template`；批处理静默写 rules 仍默认 deny
- 记录时应由你（LLM）提供 tags，并尽量附带优化标题：

```bash
ygg remember "原始长说明……" \
  --title "用户原话或原文标题" \
  --title-refined "更贴合内容的短标题" \
  --tags cpp memory performance \
  --json

# 站立偏好 → rules（显式或命中「以后一直这样」等）
ygg remember "排障失败一次后必须先 web search……以后一直这样" \
  --as rule --tags troubleshooting --title-refined "fail-once-then-web-search" --yes --json
```

- `title` 永不被脚本改写；`title_refined` 是额外的优化版标题字段
- tags 经 `graph/tag-synonyms.yaml` 归并后写入条目，并可更新 `graph/tag-graph.yaml`

## 何时自动检索记忆（触发约定）

**高置信度：自动 recall / associate / remember**

- 回顾过去：「我以前说过…」「上次那个…」
- 确认记忆：「我有没有跟你说过…」「查一下我的…」
- 记录指令：「记住这个」「写进错题本」
- 显式联想：「联想一下 git」「关联 workflow」

**中置信度：建议 associate，再必要时 recall**

- 选型/决策：「A 还是 B」「哪个更合适」
- 经验/排障语境：提到反复踩坑、历史做法

**不触发（省 token）**

- 闲聊问候、简单事实问答、已有足够上下文的连续对话
- 用户说「这次不用查记忆」「静默模式」

**强制钩子（部署后自动启用）**：`beforeSubmitPrompt` 钩子在每条用户消息提交前自动运行 `scripts/hooks/trigger_detector.py`，把检测结果（`should_trigger` + `action`）落盘到 `yggforge-runtime/cache/last_trigger.json`；`sessionStart` 注入 ygg 路由与**三源综合回答**协议。agent 回答前必须先 Read 该文件并按 `action` 路由；作答时综合模型推理、ygg 检索与联网搜索（`ygg-answer-synthesis.mdc`）。是否触发、是否真正执行 ygg 命令由 `behavior` 配置与门禁决定。本机覆盖：`yggforge-runtime/config/behavior.local.yaml`。详见 `docs/reference/triggers.md` 第 6 节。

推荐内部顺序：`ygg tag --list`（可选）→ `ygg associate --tag … --json` → `ygg recall … --json`。

## MCP 与密钥

- 结构模板：`profiles/cursor/mcp.json.example`（仅占位符）
- 真实密钥不进本仓库；仅当使用者在部署时明确要求填充时，再按其指定的私密凭据目录写入本机 `~/.cursor/mcp.json`
- 可用辅助脚本（参数为通用「secrets 根目录」，不绑定具体仓名）：

```bash
python3 scripts/cmds/ops/apply_credentials_mcp.py \
  --credentials-root <用户指定的私密凭据根目录> \
  --example profiles/cursor/mcp.json.example \
  --target ~/.cursor/mcp.json
```

## 知识联想检索与综合回答

处理用户问题 / 任务时，须综合三源（真源 `knowledge/rules/standing-preference.md`；Cursor 薄规则 `profiles/cursor/rules/ygg-answer-synthesis.mdc`）：

1. 先用模型自身理解进行推理；
2. 从对话提炼 seed tags，执行 `ygg associate --tag ...`（可用 `--hop`）；按 `last_trigger.json` 的 `action` 必要时 `recall`；
3. 联网搜索（WebSearch / WebFetch）：事实类、时效敏感类问题必须搜索；
4. 阅读 ygg 命中真源条目，把三源结果综合纳入回答，标注来源与置信度；不得仅凭 ygg 命中作答。

`skip` 时可跳过 ygg 检索省 token，但仍须模型推理 + 按需联网 + 综合作答。

索引重建：`ygg graph build`。约定见 `docs/concepts/retrieval-conventions.md` 与 `graph/README.md`。
