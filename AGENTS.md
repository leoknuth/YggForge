# YggForge 仓库维护说明

本文件约束 AI Agent 如何维护 `YggForge` 这个仓库本身。

若按仓库文档（`docs/guide/quickstart.md`、`docs/guide/deploy.md`、`ygg deploy` 等）部署或接入不成功，**十分推荐由 AI 根据报错与本仓库结构做检查和修正**；环境差异（路径、权限、symlink/junction、`*.local.json`）往往比脚本本身更容易踩坑。也欢迎人类或 AI 在遵守下文分层、晋升门禁与真源约定的前提下，自行优化完善本框架。

## 项目名称

本仓库名为 `YggForge`。

- `Ygg`
  - 来自北欧神话中的 `Yggdrasil`
  - 在本项目语境里表示连接多个 Agent、多个项目、多个知识层的共同根系
- `Forge`
  - 表示把原始材料锻造成可复用的工程资产

这个名字是刻意选择的：

- 它不是一个被动档案馆
- 它是一个有根系、可演化、可投影的工程知识系统
- 它的目标不是“存东西”，而是“连接、提炼、约束、复用”

## 使命

维护一个干净、可版本化、可跨 Agent 使用的工程知识真源，当前重点覆盖：

- C++
- 量化研究与交易系统
- 高性能系统
- 低延迟和正确性敏感的基础设施

仓库未来可能扩展到其他语言、其他工程领域和其他项目类型，不要把结构过度绑定在当前的 C++ 场景上。

## 非目标

- 不要把仓库变成泛化博客归档
- 不要把大量原始材料直接堆进主知识目录
- 不要在没有明确审核路径的情况下，把 AI 总结直接晋升为强规范

## 仓库规则

- 可部署核心包位于 `yggforge-core/`（`CORE_ROOT`）；部署时整包投影为各 Agent 下的 `yggforge-core/`
- 将 `yggforge-core/knowledge/` 视为知识真源层
- 将 `yggforge-core/profiles/` 视为面向具体工具的投影层
- 将 `yggforge-core/scripts/` 视为运维和自动化层
- 可再生产物在 `yggforge-generated/`；本机记忆与 `*.local.json` 在 `yggforge-runtime/`
- `docs/`、根 `README.md` / `AGENTS.md` 留在仓库根（`REPO_ROOT`）
- 目录边界与关系图见 `docs/concepts/layout.md`
- 文档保持短、小、可导航，优先索引和元数据，不要堆成长篇单文件
- 变更以增量方式为主，不要轻易重写稳定规则
- 每个被晋升的知识条目都应尽量标明：
  - 来源
  - 适用范围
  - 置信度
  - 最后审核时间

## 编辑约束

- 优先使用 Markdown 和 YAML
- 文件名保持稳定、可读、可预测
- 新增规则或经验条目时，若附近存在索引文件，应同步更新
- 外部来源应在 `yggforge-core/knowledge/sources/` 留下引用或原始材料
- 暂不确定的内容应先进入 draft / inbox / distilled，而不是直接进入 `rules/`

## 晋升模型

- `sources/inbox` -> 原始输入
- `sources/distilled` -> 提炼结果
- `lessons/` 或 `templates/` -> 可复用但非强制
- `rules/` -> 强约束或强推荐团队规范

进入 `rules/` 需要明确的人类确认。

## 部署原则

- 不要在知识文档中硬编码具体工具路径
- 工具差异留在 `yggforge-core/scripts/` 和 `yggforge-core/profiles/`
- 优先整包部署 `yggforge-core` → `~/<agent>/yggforge-core`，再叠加薄入口（`AGENTS.md` / `rules/`）
- 目标工具支持时优先使用 link/junction
- 生成的投影产物应保持短、小、可追踪

## 检索原则

- 优先优化小上下文窗口
- 先路由到索引，再窄范围检索
- 避免默认让 Agent 通读整个仓库
- 保护元数据完整性，便于未来按语言、领域、编译器、平台、置信度、时效性过滤

## 编码原则

- 文本文件统一使用 UTF-8
- 核心 Markdown 文档和 `AGENTS.md` 使用 `UTF-8 with BOM`
- 避免让 Windows PowerShell 把中文误读为本地代码页

## Trigger Model

`YggForge` 定义了一套触发模型：

- 显式触发：
  - `ygg status`
  - `ygg deploy`
  - `ygg import`
  - `ygg sync`
  - `ygg push`
  - `ygg ingest`
  - `ygg distill`
  - `ygg remember`
  - `ygg promote`
  - `ygg index`
  - `ygg recall`
  - `ygg dream`
  - `ygg graph`
  - `ygg project`
  - `ygg associate`
  - `ygg behavior`
  - `ygg doctor`
- 通用触发：
  - `ygg <自然语言意图>`

当用户写 `ygg` 后跟自然语言描述时，应优先把它解释为对 YggForge 功能的路由请求，而不是普通闲聊或无结构说明。

触发词说明见：

- `docs/reference/triggers.md`

## KimiClaw / OpenClaw 集成 (无 IDE Hooks 环境)

在 KimiClaw、OpenClaw 或其他无 `beforeSubmitPrompt` 钩子的环境中，由 Agent 在 `AGENTS.md` 中内化触发规则，替代 Cursor IDE 钩子的自动检测。

### 自动触发规则

Agent 每次收到用户消息时，**静默判断**是否命中 YggForge 触发意图：

**否定模式（静默跳过，不提及 YggForge）：**
- 纯问候：你好、在吗、hello、hi
- 时间日期：今天几号、现在几点
- 填充词：嗯、哦、好的、知道了
- 显式退出："这次不用查记忆"、"静默模式"

**意图模式（静默触发，简单提及）：**
- `remember`: 记住、记一下、写进错题本、以后一直这样
- `ingest`: 收进知识库、归档、收下
- `distill`: 提炼、蒸馏
- `recall`: 我以前/之前说过、上次那个、查一下我的
- `associate`: 联想、按标签联想
- `tag`: 加标签、管理标签、标签传播
- `graph`: 重建索引、graph build、建图
- `dream`: 扫描候选、找重复、该晋升什么
- `promote`: 升级成规则、晋升
- `status/deploy/sync/behavior`: 看状态、部署、同步、改策略
- `explicit_ygg`: 消息以 `ygg ` 开头
- `default_on`: 当 `default_trigger_on_chat=true` 且无匹配时，低置信度触发

**触发后的行为：**
1. 调用对应 `ygg` CLI 命令获取结果
2. 在回复中简单提及：**"YggForge已触发"**（无需额外解释）
3. 按三源综合策略（模型推理 + ygg 检索 + 联网搜索）作答

**未触发时的行为：**
- 不提及 YggForge
- 不浪费 token 于检测说明
- 正常回复

### 为什么这样设计

Cursor IDE 通过 `beforeSubmitPrompt` 钩子自动调用 `trigger_detector.py` 并落盘 `last_trigger.json`。在 KimiClaw 等云端 Agent 环境中，没有消息提交前的本地拦截机制，因此将触发规则写入 `AGENTS.md`，让 Agent 在每次对话开始时内化并执行，效果等价。

部署建议：将本段规则写入 Agent 工作区的 `AGENTS.md` 或 `SOUL.md`，Agent 即可自动获得 YggForge 触发能力，无需额外脚本或配置。


## 发布隐私边界

使用 `docs/concepts/publication-boundary.md` 的准入规则。框架可按任务授权同步；带“隐私”标签的记忆或附件不得公开，其他记忆需逐项得到用户同意。公开索引从准入内容重建，运行时、本机配置和私有历史不进入发布。
