# Codex 投影入口

请把这个知识系统当成“带路由的知识真源”，而不是一个要整库通读的说明文件。

已部署时，核心包位于 `~/.codex/yggforge-core/`（链接到仓库 `yggforge-core/`）。
下文路径均相对该核心包根目录。

## 优先级

1. 先遵守本文件中的投影约束
2. 先吸收 `profiles/common/behavior-packs/karpathy-guidelines.md`
3. 再读取 `knowledge/rules/`
4. 再读取 `knowledge/templates/`
5. 最后按需读取 `knowledge/lessons/`

重要约束：

- 本地仓库约定优先于通用默认做法
- 不要默认全库读取
- 只拉取当前任务所需的最小文件集
- 先使用全局行为约束规范执行方式，再使用项目规则约束具体内容

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

## 同步约束

- 先看最近部署模式，再决定是否需要 reverse sync
- 若当前目标通过 `link` 部署，改动已直接落在仓库，不需要额外 import
- 若当前目标通过 `copy` 或 `render` 部署，优先使用 `ygg import codex`、`ygg sync codex` 或 `ygg push codex`
- 不要把 Codex 私有路径约束写成知识真源规则

## 记忆约束

- 用户要求“记住”“写进错题本”“以后一直这样”时，优先使用 `ygg remember ...`
- 记忆先进入仓库级 `knowledge/lessons/inbox/`，而不是 Codex 私有目录
- 当一条 inbox 草稿已经足够稳定时，使用 `ygg promote <entry> lesson|rule|template`

## 知识联想检索与综合回答

处理用户问题 / 任务时，须综合三源（真源 `knowledge/rules/standing-preference.md`）：

1. 先用模型自身理解进行推理；
2. 从对话提炼 seed tags，执行 `ygg associate --tag ...`（可用 `--hop`）；必要时 `recall`；
3. 联网搜索：事实类、时效敏感类问题必须搜索；
4. 阅读 ygg 命中真源条目，把三源结果综合纳入回答，标注来源与置信度；不得仅凭 ygg 命中作答。

索引重建：`ygg graph build`。约定见 `docs/concepts/retrieval-conventions.md` 与 `graph/README.md`。
## 标准命例与独立分术

- 具名角色已配置 case_template 时，新命例先用 `ygg role case-init <role_id> <case_id>` 建英文目录；有资料的可选专项用 `case-add-track` 启用，不能拿空模板当已完成分析。
- 标准命例任务显式绑定 `record_id` 与 `stage`：`blind` 再绑定单一 `track`，仅给原始事实、本术计算、完整专业技能和安全方法投影。原 USER、旧综合、其他术报告、业务记忆与完整父会话不进入初始上下文。
- 当前聊天分术使用 `fork_turns=none` 的新 subagent；这是逻辑隔离。需要本地文件范围限制时采用 `role run --isolation enforced`，以实际收据确认，不自动降级。
- 各术原稿与证据完整保存，经 `case-freeze` 校验首判和来源后，再用 `stage=synthesis` 读冻结成果生成总览、总评、典籍映照、分歧和完整汇总。
- 回访使用 `stage=review` 读取本案批准历史与反馈，明确属于非盲复核；更正用新记录版本保留原判。不能因隔离而削减原技能方法、人格或专业输出关卡。
- CLI 与隔离契约见仓库 `docs/guide/role-cases.md`；角色模板与具体命例规范按该角色 AGENTS/SKILL 执行。
