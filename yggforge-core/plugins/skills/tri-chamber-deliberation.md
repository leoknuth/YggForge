---
id: ygg-skill-tri-chamber
title: 三庭合议（ICJ）编排技能
title_refined: "tri-chamber-deliberation skill"
type: skill
status: active
confidence: high
source: user
scope: cross-project
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - deliberation
  - agent
  - workflow
agent_targets:
  - cursor
  - codex
  - opencode
  - claude
  - openclaw
depends_on:
  - ygg-rule-tri-chamber
project_to:
  cursor: .cursor/skills/tri-chamber-deliberation/SKILL.md
  codex: .agents/skills/tri-chamber-deliberation/SKILL.md
  opencode: .agents/skills/tri-chamber-deliberation/SKILL.md
  claude: .claude/skills/tri-chamber-deliberation/SKILL.md
related:
  - ygg-rule-tri-chamber
---
# tri-chamber-deliberation（三庭合议 / ICJ）

## When To Use

当用户要求用 **三庭合议**、**ICJ**、**Independent–Critique–Judge**、**合议三轮**、
**model council**、或明确说「先各自思考再互相评议最后由基座汇总」时启用。

典型输入：

- 要解决的问题 / 任务正文
- 参与模型列表（如 `kimi, GLM, Composer, Grok`）
- 可选：是否落地改主仓、是否禁网、验收标准

本技能由**当前对话中的基座 Agent（协调者 / 裁庭）**执行编排；候选模型只做初庭与议庭。

## 范式一句话

**初庭独立成案 → 议庭交叉评议修订 → 裁庭（基座）终裁落地。**  
默认**强制联网**检索相关知识、方案、技术、官方文档/网站、权威百科与书籍等；共识≠真理，终裁须可论证。

## 角色

| 角色 | 谁 | 职责 |
|---|---|---|
| **初庭** Debater | 用户指定的每个模型各一路 runner | 隔离作答；强制联网；互不看见 |
| **议庭** Critic | 同一批模型（`resume`） | 读全员初庭答案；交叉评议；修订己案 |
| **裁庭** Judge | **仅**当前基座 / 父 Agent | 综合初庭+议庭；拍板；可选主仓落地 |

禁止：候选自称终裁；裁庭跳过初庭/议庭直接拍板（用户显式「只要裁庭」除外）。

## 输入解析（启动时必须做）

从用户消息提取：

1. **`problem`**：任务正文（去掉触发词与模型 CSV 后的剩余）。
2. **`models`**：逗号/顿号/`和`/`+` 分隔的模型名；保留重复（重复=独立并行跑）。
3. **`implement`**：是否要求主仓落地（默认：用户说「实现/落地/修改」才落地；否则只出裁定）。
4. **`web`**：默认 **on**；仅当用户明确「禁网/离线/不要搜索」时 off。
5. **`isolation`**：默认使用 Cursor `/best-of-n` 或 `best-of-n-runner` + `/worktree` 隔离；不可用则降级说明。

模型名 → Task `model` slug：以当前环境 `available_subagent_models` / 用户指定为准；未知则列出可用 slug 并请用户确认，**禁止编造**。

缺模型或缺问题：先用**一个**澄清问题补齐，再开跑。

---

## Round 0 · 裁庭预备（协调者本人做）

在派发初庭之前：

1. **联网检索简报包**（`web=on` 时强制；至少覆盖下列类别中能找到的来源）：
   - 官方文档 / 规范 / RFC
   - 官方产品或项目网站
   - 权威百科或标准教材章节
   - 同行评审论文 / 经典算法与图论/统计资料（若任务相关）
   - 近期实践综述或高质量工程文章（标注时效）
2. 用 `ygg associate`（相关 seed tags）拉取仓库真源约束。
3. 写出一页 **Briefing Pack**（给所有初庭共用）：问题复述、约束、验收、检索到的来源列表（URL+一句话）、明确禁止项。
4. 向用户短报：将跑哪些模型、三轮协议、是否落地；然后开 Round 1。

Briefing Pack 必须发给每一路初庭；不得只塞给裁庭自己。

---

## Round 1 · 初庭（并行、隔离）

### 编排

- 优先：对 `models` 中每个 token 启动一个 `best-of-n-runner`（或等价隔离 subagent）。
- **主工作树在初庭与议庭期间不得被候选修改**（与 `/best-of-n` 隔离约定一致）。
- 每路必须先 `/worktree`（或平台等价隔离）；失败则该路失败并报告，禁止回退污染主仓。

### 每路初庭强制指令（写入 subagent prompt）

```text
你是三庭合议·初庭议员（Independent）。
禁止查看或猜测其他模型的答案。

【Briefing Pack】
{粘贴 Round 0 简报}

【任务】
{problem}

【强制】
1. 自行联网搜索：官方文档、官网、权威百科、权威书籍/教材、相关论文或标准实现；列出引用。
2. 从第一性原理给出方案/参数/风险/推荐。
3. 只输出「初庭成案」：结论、论据、来源、未决问题。
4. 全部工作在本 worktree；不 push；不改主仓。
5. 返回：worktree 路径 + 成案正文。
```

### 初庭结束条件

- 全部 runner 完成或失败已记录。
- 协调者汇总为 **Answer Pack v1**（按模型分节，尽量原样保留关键结论，可压缩样板话）。
- **停住**：不要自动进议庭直到 Answer Pack v1 齐备（可短告知用户「初庭完成，进入议庭」）。

---

## Round 2 · 议庭（交叉评议）

### 编排

- 对每一路成功的初庭 runner：`resume`（或新开同模型隔离会话），投喂 **完整 Answer Pack v1**。
- 仍在各自 worktree；仍禁止改主仓。

### 每路议庭强制指令

```text
你是三庭合议·议庭议员（Critique）。
你已完成初庭。现在必须阅读全员初庭答案后再修订。

【Answer Pack v1】
{全员初庭原文或忠实摘要}

【强制结构】
1. 逐家摘要（点名每个模型）：要点 / 可取 / 漏洞
2. 共识表 vs 分歧表（至少各 1 条；若无分歧须论证「为何同质化可接受」）
3. 指出可能的「多样性崩塌」（大家共享同一错误先验）
4. 基于全员材料给出「议庭修订版」——允许改参数与优先级
5. 「少数意见」：你仍坚持但可能不被采纳的点（可空，但须显式写无）
6. 补充联网核查：针对分歧点再搜官方/权威来源

禁止：只复述自己的初庭；禁止假装没看到他人答案；禁止未经论证的虚假共识。
```

### 议庭结束条件

- 汇总 **Answer Pack v2**（各模型修订版 + 分歧表合并）。
- 再短告知用户后进入裁庭。

---

## Round 3 · 裁庭（仅基座）

由**当前对话基座**执行（不要再派一个「假领导」subagent 代替，除非用户指定 moderator 模型且环境支持）。

### 强制步骤

1. 再读 Answer Pack v1 + v2；必要时对未决事实 **再次联网** 核对。
2. 从第一性原理筛选：采纳 / 修改 / 拒绝各条建议，写清理由。
3. 输出 **裁庭裁定书**（见下方格式）。
4. 若 `implement=true`：在**主工作树**落地；跑约定验收；报告结果。
5. 若用户只要设计：停止于裁定书，不改主仓。

### 裁庭裁定书格式

```markdown
## 三庭合议 · 裁庭裁定

**问题：** …
**参与模型：** …
**联网要点：**（3～7 条关键来源）

### 终裁
（清晰可执行的决定）

### 采纳与拒绝
| 来源 | 主张 | 裁庭态度 | 理由 |
|---|---|---|---|

### 共识（经检验）
- …

### 已消解分歧
- …

### 遗留风险 / 待证伪点
- …

### 落地计划
（无落地则写「本次不改主仓」）
```

---

## 联网检索规范（默认开启）

每次初庭、议庭、裁庭在信息不足或存在分歧时必须检索，优先顺序：

1. 官方文档与规范  
2. 官方网站 / 发布说明  
3. 权威百科或标准教科书  
4. 经典论文 / 标准算法参考  
5. 高质量工程实践（注明日期与局限）

引用须可核对（URL 或书名+章节）。禁止用「大家都知道」代替来源。  
用户声明禁网时：在裁定书显著位置写「离线模式」，并降低事实置信度表述。

---

## 与 `/best-of-n` 的关系

| | `/best-of-n` | 三庭合议 |
|---|---|---|
| 默认 | 仅并行独立成案 | 初庭 + 议庭 + 裁庭 |
| 主仓 | 跑完不自动合并 | 裁庭按需落地 |
| 联网 | 视任务提示 | **默认强制** |

实现上：Round 1 应复用 `/best-of-n` / `best-of-n-runner` 隔离机制；Round 2/3 是本技能追加的协议层。

---

## 反模式（禁止）

- 跳过初庭或议庭「直接综合」  
- 议庭变成互相吹捧、无分歧表  
- 用多数票代替论证  
- 候选改主仓或 push  
- 编造不可用的 model slug  
- 裁庭只复读某一路而声称「综合」  
- 禁网时仍假装查阅了官网  

---

## 降级

| 情况 | 处理 |
|---|---|
| 仅 1 个模型 | 初庭 →（自检修订作弱议庭）→ 裁庭；向用户声明多样性不足 |
| Task 不支持某模型 | 跳过该路并报告；或征得同意后改用可用 slug / 角色视角降级 |
| worktree 失败 | 该路失败；其余继续；裁庭注明缺失 |
| 用户只要「快速」 | 可建议缩议庭为单轮，但须用户确认；默认不缩 |

---

## 调用示例

```text
三庭合议 kimi, GLM, Composer, Grok：
评估并实现 opt-plan O1–O3；要落地主仓；从第一性原理论证参数。
```

```text
ICJ with Composer and Grok — should we use hop-constrained Dijkstra or plain BFS for tag expand?
Design only, no code changes.
```

---

## Notes

- 触发与不变量见 `plugins/rules/tri-chamber-deliberation.md`（`ygg-rule-tri-chamber`）。
- 思想来源：独立判断（crowd）→ 结构化反馈（Delphi）→ 终裁（judge）；并吸收 Cursor `/best-of-n` 隔离与社区 concilium/dialectic 的分轮约束。
- Token 昂贵是预期成本；本技能优化的是疑难任务上的论证质量，不是费用。
