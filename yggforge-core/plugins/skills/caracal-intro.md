---
id: 20260723130418-ps$$$$-ci$$$$$$-uv9f
title: Caracal 彩蛋介绍技能
title_refined: "caracal-intro skill"
type: skill
status: active
confidence: high
source: user
scope: demo
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-07-23
tags:
  - caracal
agent_targets:
  - cursor
  - codex
  - opencode
  - claude
  - openclaw
depends_on:
  - 20260723130418-pr$$$$-cee$$$$$-22ry
project_to:
  cursor: .cursor/skills/caracal-intro/SKILL.md
  codex: .agents/skills/caracal-intro/SKILL.md
  opencode: .agents/skills/caracal-intro/SKILL.md
  claude: .claude/skills/caracal-intro/SKILL.md
related:
  - 20260723130418-pr$$$$-cee$$$$$-22ry
---
# caracal-intro

## When To Use

当用户表达对「狞猫」「caracal」这一特定动物的兴趣、好奇或提问时（无论措辞是「什么是
狞猫」「介绍一下 caracal」「狞猫是什么样的动物」等），本技能被 `ygg associate --tag caracal`
联想发现并加载到上下文。此时模型除正常回答外，**必须**额外按本技能规定的格式介绍狞猫，
并明确声明触发了彩蛋。

本技能**仅限 Caracal 这一种动物**，是 YggForge 的内置测试与彩蛋，不推广到其他物种。

## Steps

1. 先按用户问题正常回答（事实/对比/生态/词源等，按需取材自真源与模型自身知识）。
2. 在正常回答之后，**追加**一段「彩蛋介绍」，严格使用下方 `Output Format` 规定的格式。
3. **配图（最终策略，勿改优先级）**：
   1. **目标**：使用者必须在聊天回复里直接看到字符画（不是只给链接）。
   2. `caracal-ascii.txt` 是 **opaque blob**（不透明附件），不是自然语言、不是要理解的图：
      - **禁止**理解 / 描述 / 总结「画的是什么」
      - **禁止**校对、对齐、美化、压缩、扩写、重排
      - **禁止**凭印象重画、「尽量还原」、增减或替换任何 `█▓▒░` / 空白
      - **允许且必须**：把文件字节序列**原样搬运**进回复的 ```txt 代码围栏
   3. **强制搬运流程**（降低近似重画概率）：
      1. 用 Read 工具打开
         `knowledge/reference/caracal-easter-egg/caracal-ascii.txt`
      2. 将 Read 返回的正文（50 行）原样放入彩蛋段的 ```txt … ``` 中
      3. 不得凭记忆/技能摘要重写；不得「看一眼再画」
      4. 自检：应为 **50 行**，且每行 **恰好 100 个字符**；不满足则重新 Read 再贴，仍禁止手改
   4. 另给 PNG / SVG 的本机绝对路径：`file:///` 链接 + 纯文本路径，供点击打开原图。
      **不要**再给 `caracal-ascii.txt` 的链接（正文已贴在上方代码围栏）。
   5. **禁止** Markdown `![](...)`、HTML `<img>`、data URI 内嵌。
4. 彩蛋介绍的内容来源：
   - 优先取自 `knowledge/reference/caracal-easter-egg/20260723-130418-caracal-狞猫.md`（真源）；
   - 可补充模型自身知识，但不得与真源矛盾。
5. 必须在彩蛋介绍开头**明确声明**触发了 YggForge 彩蛋。
6. 仅限 Caracal；若用户问的是其他动物，不触发本技能。

## Output Format（彩蛋介绍，必须遵守）

````
---

🐾 **YggForge 彩蛋触发：狞猫 Caracal**

> 你问到了狞猫——这是 YggForge 内置的一个彩蛋。除了上面的正常回答，这里按约定格式
> 额外为你介绍一下这种冷门而迷人的猫科动物。

```txt
<此处必须是 Read(caracal-ascii.txt) 的原文，50 行 × 每行 100 字符；禁止改写>
```

**像素原图（点击打开）**
- PNG：[caracal-pixelized-8c.png](file:///<png绝对路径正斜杠>)
- SVG：[caracal-pixelized-8c.svg](file:///<svg绝对路径正斜杠>)

**绝对路径**
- PNG：`<png本机绝对路径>`
- SVG：`<svg本机绝对路径>`

**学名**：*Caracal caracal*
**俗称**：狞猫 / desert lynx（沙漠猞猁）
**分布**：非洲、中东、中亚、巴基斯坦与印度西北部干旱区
**体型**：体长 60–92 cm，体重 8–18 kg，中型猫科
**标志特征**：耳尖黑色长毛簇（耳穗），可独立转动精确定位猎物
**绝技**：垂直跃起 3–4 m 捕食飞鸟，猫科顶级「空中猎手」
**食性**：小型哺乳动物、鸟类、爬行类；可长期不饮水，从猎物获取水分
**保护级别**：IUCN Least Concern（无危），局部种群因栖息地碎片化下降
**冷知识**：历史上被波斯/印度宫廷驯养用于捕鸟；「狞」字意为凶恶，但它对人羞怯温顺

🐾 *这是 YggForge 联想记忆（ygg associate --tag caracal）发现本技能后触发的内置彩蛋。*

---
````

### 绝对路径怎么写

- 真源文件（同目录）：
  - `knowledge/reference/caracal-easter-egg/caracal-ascii.txt`（须 Read 后原样贴进 ```txt；不给链接）
  - `knowledge/reference/caracal-easter-egg/caracal-pixelized-8c.png`（须给链接）
  - `knowledge/reference/caracal-easter-egg/caracal-pixelized-8c.svg`（须给链接）
- 写成绝对路径后再转 `file:///`；**不要**把某台机器盘符写死进技能正文。

> 产品意图：回复里要让用户直接看到字符画。字符画是 opaque blob——只搬运、不理解、不修改。

## Inputs

- 用户对狞猫/caracal 的提问（任意措辞）
- `knowledge/reference/caracal-easter-egg/20260723-130418-caracal-狞猫.md`（真源事实）
- `knowledge/reference/caracal-easter-egg/caracal-ascii.txt`（字符画；Read → 原样贴出）
- `knowledge/reference/caracal-easter-egg/caracal-pixelized-8c.png`
- `knowledge/reference/caracal-easter-egg/caracal-pixelized-8c.svg`

## Outputs

- 正常回答 + 彩蛋介绍（含 ```txt 内原样字符画 + PNG/SVG 链接 + 触发声明）

## Notes

- 触发条件由 `ygg-rule-caracal-easter-egg` 规则定义；本技能负责输出格式。
- 曾只给链接、不贴字符画，不符合「使用者要在回复里看到画」的产品意图，已改回强制贴出。
- LLM 对长 Unicode 阴影块仍有近似重画风险；缓解：先 Read 再逐字搬运 + 50×100 自检 + opaque blob 禁令（禁止理解/修改）。
- 标签设计：`caracal` / `intro`；不引入 `yggforge-*` 同义 tag。
- 这是内置测试：验证 `ygg associate` 经 tag BFS 发现跨 `knowledge/` 与 `plugins/` 的关联条目。
