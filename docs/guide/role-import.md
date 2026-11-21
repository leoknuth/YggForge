# 角色保真导入与原生分层

日期：20261121。本文是通用导入契约，实际角色集合、案例与逐文件审计由管理者在受控资料中保存。

## 目录

- [完整方法承接](#完整方法承接)
- [原生目录与职责](#原生目录与职责)
- [默认入口与工作流](#默认入口与工作流)
- [静态资源和可变资料](#静态资源和可变资料)
- [逐项合并与异常输入](#逐项合并与异常输入)
- [退役版本与许可](#退役版本与许可)
- [验证与能力状态](#验证与能力状态)

## 完整方法承接

导入先清点五根件、直接或根部 SKILL 及支持树，再逐项读取与对照。专业方法、人格语气、默认路由、规范关卡、格式要求、产物工序和工具输入输出契约以完整原正文为主体。源文件很长不是改写成通用摘要、精选少量技能或短入口的理由。

AGENTS、IDENTITY、SOUL、USER、TOOLS 保留完整有用内容；旧平台最高准则、服务状态、路径、记忆工具及目录章节可做必要且精确的宿主适配，并审计原因和保留范围。USER 原档案注明事实来源与时效，新任务主体单独核对。

SKILL 正文回到其实际原目录名，原直接/根部有效入口全面处理；嵌套模板、style、脚本、字体和 reference 保留原父树。已存在的有效技能增量融合，同名不同版本不覆盖专业大段内容。 额外source-skill/source-method原包副本在正式入口完整承接后清除；先逐段反路径适配核覆盖和署名，独有补充正式合入对应专业reference，不能只换名保留包装。原有效根部 SKILL 可以按其原位置注册，不为统一目录而丢失入口。

## 原生目录与职责

```text
roles/role-id/
  AGENTS.md / IDENTITY.md / SOUL.md / USER.md / TOOLS.md
  role.yaml
  skills/skill-id/SKILL.md
  skills/skill-id/{references,scripts,assets,许可}
  records/类别/实体/STATE.md
  records/类别/实体/{业务数据,脚本,文档,附件,资产,产物}
  memories/notes/{reference,templates,decisions,rules,lessons/inbox,sources}/
  memories/graph/
  memories/summary.md
```

业务文件直接按实际类别与实体进入 records，不留下整包导入项目、raw source 或仅改名的备份层。记录实体有可调度 ID 与 STATE，包含资料索引、实际状态、原时点、已核范围和待办。

稳定方法与纯 SOP 进入现役 skills；领域知识、决策和真实事件进入自身 notes 的相应类型。真实客户、学情、用户变量、生成反馈和市场数据进入对应实体，不能混为静态 skill 资源或跨项目用户事实。logs、data 等名称不能代替内容分类。

临时快照、凭据、客户端、本机配置、缓存和收据在运行层；长期业务目录和原始记录保持独立。逐文件来源关系由导入审计保存，不用复制整包作为唯一追溯方式。

## 默认入口与工作流

角色配置采用现役完整 SKILL 路径；默认首入口和工作流必须引用本角色注册技能。

```json
{
  "skills": ["skills/topic-router/SKILL.md", "skills/evidence-review/SKILL.md"],
  "default_skills": ["skills/topic-router/SKILL.md"],
  "skill_workflows": {"evidence-review": ["skills/topic-router/SKILL.md", "skills/evidence-review/SKILL.md"]},
  "records": {"example-record": {"path": "records/research/example-record", "state": "STATE.md"}}
}
```

示例目录必须先有对应完整方法及 STATE。运行时显式 skills 优先；否则保留 default_skills，再完整加入 workflow，自动匹配预算仅限制额外可选技能。原角色的综合流程与子技能关系需要在配置和正文同时承接，不能因只载一个子技能就宣布综合工作已完成。

目录路由只有当前真实结构。AGENTS 原目录章节应直接改成现役 skills、records 与 memories；只追加适配说明而留下旧空间契约不算完成内化。

## 静态资源和可变资料

metadata.resources 相对技能根声明实际文件或安全子树。未声明时安全扫描，[] 只提供入口，非空列表只投影所声明的支持资源；缺失、越界或包含禁项时明确报错，不扩大范围。

```yaml
---
name: evidence-review
description: 按专业流程检查输入来源、完整性和口径。
metadata: {"tags":["research","review"],"requires":["python"],"availability":"method-not-executed","resources":["references","scripts/check_inputs.py","LICENSE"]}
---
```

路径是契约示意，应填写实际已有支持文件。保留原 metadata 与署名；名称相似但分工不同的工具、方法、模板和 API 层不能简单去重。

实际附件及用户记录由 task.files 在记录或显式外部项目根内选取。每个项目限定 notes 使用真实 record/project 作用域；通用方法无个案事实时可标为 role/cross-project。角色摘要是带来源的派生资料，不吸收完整客户库或学情库作为当前身份。

## 逐项合并与异常输入

逐文件审计至少包括原路径、原 hash、实际 native 目标和 hash、适配原因、修改段落、完整正文覆盖、许可、异常及验证状态。删除或移动前核 resolved 路径落在本轮授权角色范围；未覆盖有用内容不能删。

源入口损坏、只有测试占位或缺少方法时单列异常。若可从同一实现与可靠版本完整修复，保留证据、支持文件及修复来源；否则不注册为完整能力。注册数量不能掩盖源损坏，补一个 name/description 或简短包装不能作为专业恢复。

乱码只在可逆且无路径冲突时修复，并记录原名。源凭据不进入长期文件，脱敏审计不复述密钥。用户明确排除的材料按原范围处理，不能自行改名、转换或补造另一来源。

## 退役版本与许可

依据来源中的现役/退役/废弃标记及真实引用判断。用户明确授权删除已退役废技能时，清退额外恢复的废版本、旧包装、空副本和悬空路由，不把它们改名塞进 library 或 notes。保留真实业务/研究记录与当前被声明使用的完整方法。

现役名称含 archive、history、cache 或旧平台词并不自动等于废技能。许可与必要署名按真实适用文件保留；重复孤儿许可只有在现役完整副本及适用范围确认后才可清除。MIT、专有、非商业与未声明许可分别识别，不能将整包统称开源或可商用。

## 验证与能力状态

完成内化需核角色注册、默认/工作流引用、完整正文、资源路径、原生记录 STATE、notes 作用域、源/目标覆盖以及图和 summary 一致指纹。源方法、静态结构、可执行依赖、认证、真实查询与实际业务验收分别留证。

源工具未配置时保留完整接口契约并说明实际状态；不自动假称服务连通，不用 ZAI 聊天、模拟或自动 Mock 响应填真实数据缺口。模拟功能可按明确模式保留，标签贯穿输入、计算和输出。

prepare 只准备；模型执行需实际 backend 收据。enforced 以真实落实的文件范围为准，不称为网络隔离；普通 subagent 仍是逻辑上下文方式。回归与全文件复核按当期收据报告，未跑的业务不写为已可用。

参见 [角色资源说明](role-resources.md)、[配置契约](../../yggforge-core/schemas/role.schema.yaml) 和 [发布边界](../concepts/publication-boundary.md)。
