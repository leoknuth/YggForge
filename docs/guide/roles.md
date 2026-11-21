---
tags:
  - roles
  - guide
---
# 伙伴角色使用指南

更新日期：20261121。命令从仓库根运行；角色的专业正文、实际注册和运行收据各自承担不同证据职责。

## 目录

- [角色文件与发现](#角色文件与发现)
- [完整首入口与工作流](#完整首入口与工作流)
- [准备角色与记录上下文](#准备角色与记录上下文)
- [双路联想与角色记忆](#双路联想与角色记忆)
- [联合任务与结果交接](#联合任务与结果交接)
- [执行与隔离](#执行与隔离)
- [验证与故障检查](#验证与故障检查)
- [保存与发布](#保存与发布)

## 角色文件与发现

每个角色由受信注册的 `role_id` 绑定自己的 `role.yaml`、AGENTS、IDENTITY、SOUL、USER、TOOLS、skills、records 和 memories。五根件承接完整人格、专业方法、默认路由和质量关卡；旧平台断言、路径及目录章节按当前真实结构精确适配，不把长方法改成通用短入口。

角色的 name、description 和领域 tags 供协调者发现。任务 tags 则用于本次技能选择及知识联想，两类标签分别维护。多个 `--tag` 要求全部命中；目录筛选不执行模型，也不取得另一角色的私有资料。

```text
ygg role list
ygg role list --brief
ygg role list --brief --tag research
ygg role list --brief --tag research --tag data
ygg role show <role-id>
ygg role check <role-id>
```

`--brief` 省略大目录清单并返回 skill_count、record_count；角色描述保持完整。配置契约见 [role.schema.yaml](../../yggforge-core/schemas/role.schema.yaml)。共同准入和预算由管理配置约束，角色设定、标签和检索命中不能自行扩大准入。

## 完整首入口与工作流

`role.yaml.skills` 注册现役 SKILL 的完整路径。`default_skills` 保存该角色原设定要求的首入口；`skill_workflows` 将一个工作流 ID 映射到本角色已注册技能列表。原角色有路由器、场景判定、确认轮、质量门或交付工序时，按完整专业协议执行。

技能选择的顺序是：

1. 本次 `skills` 或 `--skill` 显式选择优先，完整加载指定入口，不能被默认或自动命中替换。
2. 未显式指定技能时，先加载 `default_skills`。
3. 指定 `workflow` 或 `--workflow` 时，再完整加载该工作流全部入口；自动技能数量预算不裁掉默认首入口或工作流。
4. 未指定工作流时，再按任务标签与描述选择相关的可选技能。预算只限制这一步。

```text
ygg role prepare <role-id> --task "按完整工作流复核材料" --project-id <record-id> --tag research --workflow <workflow-id>
ygg role run <role-id> --task-file <task.json> --workflow <workflow-id> --backend codex --isolation enforced
```

显式选择单技能就是明确改变本轮技能范围。若任务要求原默认综合流程，不能仅选一个子技能并声称完整执行了该综合流程。大型专业正文保持在 SKILL 与原必要 reference 树中；触发后按原路由深入所需部分。

## 准备角色与记录上下文

分轨独立命例使用显式 `record_id`、`track`、`stage` 与标准 CASE 清单，流程见 [分轨命例与独立分析](role-cases.md)。该模式将资料、方法记忆和安全设定投影为本轨白名单，全部轨道冻结后才综合；一般角色任务仍按下述完整上下文契约执行。

任务 JSON 支持 task_id、prompt、project_id、tags、project_root、files、skills、workflow，以及联合任务的 roles、dependencies；标准分轨命例另外使用 record_id、track、stage、references。tags 必须来自当前任务。

`role.yaml.records` 用固定 ID 映射 `records/<类别>/<实体>/` 和 STATE。`project_id` 匹配自身已注册记录时恢复 `record_state`，可省略 project_root；它仍是内部知识作用域字段。外部代码项目继续用显式 project_root，API 字段不因业务目录改名而改成另一套名称。

```json
{
  "task_id": "example-review",
  "prompt": "按该角色原流程检查本轮明确选定的资料",
  "project_id": "example-record",
  "tags": ["research", "review"],
  "workflow": "evidence-review",
  "files": ["data/input.json", "scripts/check_inputs.py"]
}
```

示例 ID 和文件需替换为实际注册及授权值。files 只加载记录或外部项目根内明确选定的相对文件。记录目录清单和 STATE 提供定位，不能自动变成全部业务数据的授权子集，也不能读取另一角色记录或自身非记录私有目录。

ContextBundle 分开保留完整 AGENTS、IDENTITY、context_files、获选 skills、role_summary、shared_hits、role_hits、record_state 和非敏感工具状态。record_state 含完整 STATE、文件清单及 `verification=record-state-is-context-not-confirmed-fact`。`role list --brief` 的 record_count 来自实际注册目录。

准备快照在内部使用 `record/STATE.md` 与选定文件的 record 相对层次；这是执行快照，不是长期业务目录。文本给完整所选正文，支持的二进制给位置、哈希和大小；资产准备后变化时要求重新加载。大任务资料会明确拒绝或要求形成任务窗口，不能静默截成看似完整的正文。

## 双路联想与角色记忆

```text
ygg graph build --role <role-id>
ygg graph check --role <role-id>
ygg associate --role <role-id> --space dual --tag research --tag review --json
ygg recall --role <role-id> --query "关键词" --project <record-id>
ygg remember --role <role-id> --project <record-id> --note "有来源的结论" --title "标题" --source agent --scope <record-id> --confidence low --yes
```

最后一条只在本轮已授权记录经验时使用；已有条目的更新和删除使用同角色 `--update-entry`、`--delete-entry`，先检索、串行写入、再复读。

shared_hits 只来自获准共享路径，role_hits 只来自本角色 notes；结果保留 space_id、entry_id、project_id、状态、来源指纹和时效。命中正文按检索预算窄读并明确标注 truncated，随后按相关路径继续阅读。角色描述、五根件、获选 SKILL、STATE 和已有 summary 的正文在加载层不截断。

角色暂不支持可选 by-tag 导览：角色图与 --with-by-tag 组合在写入前拒绝；专属 catalog、tag-inverted 和 associate 可用。

summary 是带来源的派生摘要，全文加载不等于把全部原 notes 注入提示。项目事实保留对应 project_id；客户、学情、持仓和历史结果不因导入或摘要而成为当前用户事实。边权表达相关性，不能代替证据置信度或专业验证。

## 联合任务与结果交接

```text
ygg task run --task-file docs/examples/roles/financing-task.json --backend prepare --isolation logical
ygg task run --task-file docs/examples/roles/financing-followup-task.json --backend codex --isolation enforced
```

示例按角色级 dependencies 调度：无依赖任务可并行，有依赖则先完成前序，再交接获准模型输出。金融与法律示例分别检查经济口径和合同条件；示例材料不能生成真实客户结论。

交接保留前序 role_id、run_id、状态和实际完成的 output。另一角色完整上下文、摘要、私有命中和原目录不会作为前序结果交换。前序失败时保持联合任务失败；prepare 只准备，不虚构模型结论。

## 执行与隔离

prepare 输出逻辑上下文。当前聊天原生 subagent、CWD、worktree 和角色提示词本身不提供操作系统文件隔离。

codex backend 使用独立运行器和获准快照。enforced 在 Linux 使用 Landlock，Windows 经 WSL 原生临时工作区执行；请求能力未落实时拒绝，不自动降为 logical。实际隔离范围以运行收据为准，文件边界、工具权限和网络能力分开说明；正常模型服务连接不称为网络隔离。

运行器保留 backend、请求与实际隔离、run_id、状态、诊断和真实结果。输出回收拒绝链接与特殊文件；凭据和本机配置不会变成长期角色资料。默认 timeout 为 180 秒，复杂流程可按命令帮助调整到允许范围。

## 验证与故障检查

注册入口、资料完整、上下文准备、模型执行、依赖连通和业务验收是不同状态。新一轮源码与数据变更后的跨平台回归和全文件复核，以协调者当期收据为准；旧精选数量、旧入口长度或早期测试结果不替代当前验收。

- 加载失败：核对 ID、入口、默认/工作流引用及资源声明；不回退全局空间。
- 记录失败：核对 record ID、路径与 STATE；未注册 project_id 只是知识作用域，不会自动创建实体。
- 资源失败：核对实际静态树及选定 files；不靠名称扩大读取范围。
- 图或摘要过期：刷新本角色并核来源指纹；派生物失败时保留已保存原结果并明确待修。
- 执行失败：先核当前进程、日志、收据和产物，不把 prepare 或未知写操作当完成。
- 源工具缺口：保留完整接口契约，分别记录依赖、安装、认证和真实查询状态，不能用聊天生成或 Mock 代替真实数据。

## 保存与发布

管理员配置 roles.defaults.json 的 git_storage.enabled 决定角色提交入口是否启用。公共框架默认关闭且不分发实际角色数据，部署到管理者工作库后按已有授权开启。role commit 只暂存指定角色目录，拒绝混入其它任务暂存内容，先核图与摘要；一般框架维护由协调者单独收尾。memory.auto_refresh 控制保存后的派生刷新，tag_add_mode 只管理本角色标签；shared: 技能须在 allowed_shared_skill_paths 内。

实际完成结果以 agent 来源、项目作用域和低置信度草稿保存到自身 notes/lessons/inbox，刷新自身图和摘要；未经门禁不升为强规则。多个角色不并发操作同一 Git index，由协调者按既有授权串行保存一致版本。

```text
ygg role commit <role-id> <other-role-id> --push
```

实际角色配置、档案、技能、records、memories、图、摘要与附件属于私有资料集合。通用框架及通用导入/资源说明按 [发布边界](../concepts/publication-boundary.md) 同步；真实角色树和案例评估不随通用文档发布。

存储与执行两图见 [伙伴角色架构](../concepts/role-partners.md)，导入处置见 [角色导入指南](role-import.md)，文件契约见 [角色资源说明](role-resources.md)。
