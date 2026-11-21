# 伙伴角色使用指南

更新日期：20261121。命令从仓库根运行；以命令帮助、角色检查和运行收据判断实际执行状态。

## 目录

- [角色文件与检查](#角色文件与检查)
- [准备双路上下文](#准备双路上下文)
- [图、检索与记忆](#图检索与记忆)
- [金融法律联合任务](#金融法律联合任务)
- [执行模式](#执行模式)
- [保存与故障检查](#保存与故障检查)
- [当前验收与限制](#当前验收与限制)
- [私有 Git 保存](#私有-git-保存)

## 角色文件与检查

私有工作库可创建 finance-expert 与 legal-expert 角色；本公共框架不附带任何实际角色配置或记忆。每个角色有 role.yaml、AGENTS.md、IDENTITY.md、skills 和 memories；后者采用全局 knowledge 的类型分层，并有自己的标签图、索引和摘要。

role.yaml 使用 JSON 兼容 YAML，契约见 yggforge-core/schemas/role.schema.yaml。管理者共享准入和默认预算位于 config/roles.defaults.json；角色选择只能落在准入范围内。

```text
ygg role create finance-expert --name 金融专家 --description 融资成本与现金流分析
ygg role create legal-expert --name 法律专家 --description 合同与法律来源核查
ygg role list
ygg role show finance-expert
ygg role check finance-expert
ygg role check legal-expert
```

初始化方法条目标记 source=example，不含真实企业、合同、金额或用户偏好。真实任务需提供自己的 project_id 和授权资料。

## 准备双路上下文

```text
ygg role prepare finance-expert --task-file docs/examples/roles/financing-task.json
ygg role prepare legal-expert --task-file docs/examples/roles/financing-task.json
```

检查 context、role_summary、shared_hits 和 role_hits。相同任务使用相同种子标签，两者分别命中自己的示例方法；共同命中只来自获准共享路径。每条记录保留 space_id、entry_id、project_id、source_fingerprint 与状态。

prepare 不执行模型。当前聊天的主代理可把准备好的上下文交给对应 subagent；实际结果与准备收据分别记录。

task 文件接受 task_id、prompt、project_id、tags、roles、dependencies、project_root、files、skills。自身已注册项目可通过 project_id 选择并省略 project_root；外部项目须显式给出 project_root。files 为项目根内明确选定的相对路径，保留原目录层次；任务资料不能指向另一角色目录或自身的非项目私有目录。skills 可显式选择本次使用的技能。

## 图、检索与记忆

```text
ygg graph build --role finance-expert
ygg graph check --role finance-expert
ygg associate --role finance-expert --space dual --tag agent --tag financing --json
ygg associate --role legal-expert --space dual --tag agent --tag financing --json
```

角色读写固定在自身 memories；全局命令保持全局语义。role 参数用于选择受信角色，不作为模型自由声明的访问权限。图、同义词和缓存分别维护，related 不自动穿透其它角色。

新经验通过显式角色记忆命令写入自身 notes/lessons/inbox，保留来源、项目、日期和确定程度。整理、晋升与自动刷新绑定同一角色，不静默写全局 inbox。

自定义日期采用 YYYYMMDD 字符串。长期 notes、graph 和 summary 随私有 Git 保存；临时会话、锁、缓存和投影留本地。

## 金融法律联合任务

并行例子：

```text
ygg task run --task-file docs/examples/roles/financing-task.json --backend prepare --isolation logical
```

金融角色说明现金流和费用口径，法律角色说明合同版本、法域和条款条件。示例没有真实合同和数值，不能生成真实项目结论。

前序依赖例子：

```text
ygg task run --task-file docs/examples/roles/financing-followup-task.json --backend prepare --isolation logical
```

dependencies 为 {"finance-expert": ["legal-expert"]}。实际执行时先处理法律角色，再把获准模型输出交给金融角色。prepare 只声明依赖顺序，不能把另一角色的完整上下文、摘要或私有命中当作交接结果；评估实际前序输出须选择可用执行 backend。

这里使用角色级依赖，不提供任意 steps 工作流；独立角色可并行，有依赖则顺序交接。

## 执行模式

```text
ygg role run finance-expert --task-file docs/examples/roles/financing-task.json --backend prepare --isolation logical
ygg role run finance-expert --task-file docs/examples/roles/financing-task.json --backend codex --isolation logical
ygg role run finance-expert --task-file docs/examples/roles/financing-task.json --backend codex --isolation enforced
```

prepare 默认只产生上下文包。codex backend 使用外部运行器，收据记录 backend、请求隔离和实际隔离。logical 不承诺操作系统访问隔离；enforced 必须通过能力检查，不支持则拒绝，不能自动降级。

文件、进程、工具和网络的限制，以运行器已经落实的能力为准，不把文件限制泛化为所有能力都已隔离。

## 保存与故障检查

run/task 的实际完成结果保存到本角色长期记忆，并刷新角色图与摘要；prepare 只准备，不保存虚构任务结论。角色不会在每个子任务里并发执行 Git。完成一轮工作后由协调者串行收尾：

```text
ygg role commit finance-expert legal-expert --push
```

该入口只汇总指定角色目录，保持角色配置、notes、graph 和 summary 的一致私有版本；一般框架代码维护仍由主任务收尾。

- 加载失败：核对 ID、目录、入口和技能，不改成全局空间继续。
- 共享路径拒绝：核对管理者准入和角色选择，不靠参数扩大权限。
- 图或摘要过期：刷新本角色来源与索引，不把旧摘要当最新事实。
- 写锁超时：检查其它宿主的更新，不直接删其他写入者的锁。
- 执行失败：保留实际 backend 和错误，不将 prepare 当模型完成。
- 公共发布：实际角色的配置、档案、技能、projects、memories 及其附件固定拒绝；私有 Git 由协调者串行保存。

角色空间说明见 [角色知识空间](../concepts/role-spaces.md)；渐进技能、项目资料和工具状态见 [角色资源指南](role-resources.md)。


## 当前验收与限制

20261120 已验证角色注册、双路上下文、记忆增改删和晋升、独立图与摘要刷新、角色标签管理及依赖结果交接。金融与法律角色使用独立受限 Codex 实例完成了短链验收，结果各自保存为 agent 来源的低置信度项目草稿，不作为强规则。

enforced 在 Linux 使用 Landlock；Windows 通过 WSL 执行。只把获准入口、技能、共享命中、自身命中和摘要送入 WSL 原生临时工作区，模型结果由可信监督器回收至本机运行目录。原始私有角色目录不直接开放给模型。绝对路径、链接和 shell 子进程越界读取已验收；输出回收不跟随链接或读取特殊文件。执行结束清理临时工作区，认证与配置快照启动后移除，不进入长期记忆或 Git。

这提供文件范围隔离，不把正常模型服务网络连接称为网络隔离；原用户 MCP 配置不加载到受限实例。prepare 与当前聊天原生 subagent 仍属于逻辑上下文准备，不能声称获得操作系统权限隔离。

复杂任务可能超过默认 180 秒，调用者可用 --timeout 调整。首次较长示例曾触发金融后续阶段超时；后续短链验收两角色均完成，失败状态不会伪装成已完成的联合任务。

角色暂不支持可选 by-tag 导览：--with-by-tag 与角色图组合会在写入前拒绝；专属 catalog、tag-inverted 和 associate 均可用。

## 私有 Git 保存

roles.defaults.json 的 git_storage.enabled 由管理者启用。role commit 只暂存指定角色目录，拒绝混入其它任务暂存内容，并核对图和摘要后提交。公共框架分发默认关闭角色 Git 保存且忽略实际 roles 数据；迁入管理者确认的私有工作库后再启用此项。

memory.auto_refresh 控制保存后的自动图与摘要刷新，tag_add_mode 只控制角色自己的新标签，不授权全局图。角色不能自动镜像全局 inbox；模型结果固定 agent 来源和草稿状态。共享技能引用可使用 shared: 前缀，但须位于管理者 allowed_shared_skill_paths 准入范围。


## 角色发现与静态资源声明

角色配置可用 tags 提供发现标签。`ygg role list --brief` 只显示说明、标签和技能／项目数量；多个 `--tag` 要求全部命中，只筛候选，不执行角色或扩大权限。

技能 metadata.resources 可声明自身目录内实际存在的静态文件或子目录；空数组不给支持资料，缺省保持安全扫描。学情、客户记录、会话和运行状态留在自己的记忆或项目，不混入技能静态资源。明确选定的字体、音视频与演示文件作为二进制资产投影，提供位置和指纹，单个项目资料仍限32MiB。

导入分层、来源记录与资源边界见 [角色导入指南](role-import.md)。
