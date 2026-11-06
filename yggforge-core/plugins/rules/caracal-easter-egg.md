---
id: 20260723130418-pr$$$$-cee$$$$$-22ry
title: Caracal 彩蛋触发规则
type: rule
status: active
confidence: high
source: user
scope: demo
channel: local
recorded_at: 2026-07-23
last_reviewed: 2026-11-06
tags:
  - caracal
always_apply: false
projection:
  - cursor
  - codex
  - opencode
  - claude
  - openclaw
related:
  - 20260723130418-ps$$$$-ci$$$$$$-uv9f
---
# Caracal 彩蛋触发规则

## 目录

- [触发与呈现](#触发与呈现)
- [图片优先与字符画兜底](#图片优先与字符画兜底)
- [适用边界](#适用边界)

## 触发与呈现

当联想检索因用户对「狞猫 / caracal」的兴趣同时发现本规则与
caracal-intro 技能时，先正常回答问题，再追加彩蛋，并声明
「YggForge 彩蛋触发：狞猫 Caracal」。

## 图片优先与字符画兜底

按当前宿主实际支持的呈现能力选择，不要求用户逐次确认：

1. 支持对话内图片且资源存在时，优先显示 caracal-pixelized-8c.png。
   宿主明确支持 SVG 时，也可显示 caracal-pixelized-8c.svg。
   可使用原生图片输出或宿主支持的 Markdown 图片语法，引用本机绝对路径。
2. 图片已经在对话中显示时，不重复贴字符画。原图链接可作为补充，
   仅给链接不算图片已经显示。
3. 宿主不支持图片、资源缺失，或无法确认可显示时，以字符画兜底：
   先读取 caracal-ascii.txt，再将正文原样放入 txt 代码围栏。
   字符画为不透明附件，不解释、校对、重画或改动；保持 35 行、每行 64 字符。
4. 图片呈现失败后，若宿主提供明确失败结果或用户反馈不可见，
   改用上述字符画兜底。
5. 路径按当前核心包位置解析，不写死某台机器的盘符、用户目录或工具私有目录。
   链接使用宿主支持的本机文件语法，不强制 file:///。

资源位于 knowledge/reference/caracal-easter-egg/。
完整输出约定见 plugins/skills/caracal-intro.md。

## 适用边界

- 仅限狞猫，不推广到其他动物。
- 彩蛋不替代正常回答。
- 用户明确要求静默、禁彩蛋或字符画时，尊重本次偏好。
