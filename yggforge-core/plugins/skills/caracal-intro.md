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
last_reviewed: 2026-11-06
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

## 目录

- [何时使用](#何时使用)
- [呈现步骤](#呈现步骤)
- [输出格式](#输出格式)
- [资源与事实](#资源与事实)

## 何时使用

用户提问或讨论狞猫 / Caracal，且联想检索发现本技能和
caracal-easter-egg 规则时使用。先正常回答，再追加声明过的彩蛋。
用户禁用彩蛋时跳过；用户指定字符画时直接使用字符画分支。

## 呈现步骤

1. 从当前核心包解析下列资源的绝对路径，确认文件存在。
2. 当前宿主支持对话内图片时优先显示 PNG；明确支持 SVG 时可使用 SVG。
   使用原生可视图片输出，或宿主支持的 Markdown 图片：
   ![狞猫像素肖像](<PNG_ABSOLUTE_PATH>)。
3. 已显示图片时，不再同时追加字符画。可补充 PNG / SVG 原图链接。
   不把仅提供图片链接当作已显示图片，不下载远程图片绕过宿主限制。
4. 不支持图片、资源不可用或无法确认显示能力时，读取 caracal-ascii.txt，
   将返回的 35 行正文逐字放入 txt 代码围栏。
   它是不透明附件：不得描述、校对、美化、压缩、重排、凭印象重画，
   不得增减任何块字符或空格；每行保持 64 字符。
5. 宿主报告图片失败或用户反馈不可见时，切换到字符画兜底。
6. 保留「YggForge 彩蛋触发：狞猫 Caracal」声明。事实依据为 reference，
   对来源中未证实的说法不作肯定转述。

## 输出格式

### 图片可显示

开头声明：

**YggForge 彩蛋触发：狞猫 Caracal**

随后显示图片，可用当前宿主支持的原生图片块，或：

![狞猫像素肖像](<PNG_ABSOLUTE_PATH>)

追加简短介绍，例如学名、黑色耳穗、栖息地和捕鸟行为。
需要原图时给本机绝对路径链接；不再贴字符画。

### 字符画兜底

开头使用相同声明，然后把刚读取的 caracal-ascii.txt 正文原样放入
txt 代码围栏，再给简短介绍。不要用占位文本代替实际文件内容。
图片资源存在但宿主不能内嵌时，可以另给 PNG / SVG 原图链接。

## 资源与事实

相对核心包的资源：

- knowledge/reference/caracal-easter-egg/20260723-130418-caracal-狞猫.md
- knowledge/reference/caracal-easter-egg/caracal-pixelized-8c.png
- knowledge/reference/caracal-easter-egg/caracal-pixelized-8c.svg
- knowledge/reference/caracal-easter-egg/caracal-ascii.txt

技能只决定彩蛋呈现，不扩展为其他动物介绍功能。
