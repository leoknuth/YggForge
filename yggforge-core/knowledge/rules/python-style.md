---
id: 20260714144840-kr$$$$-psb$$$$$-qr00
title: Python Style Baseline
type: rule
status: active
confidence: high
source: agent-profile
scope: Python 源码风格与注释
last_reviewed: 2026-07-14
owners:
  - team
tags:
  - python
  - style
keywords:
  - Google Python Style Guide
  - 中文注释
related:
  - 20260714144840-kr$$$$-$$$$$$$$-oq6u
  - 20260701165030-kr$$$$-cb$$$$$$-qppv
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 编写或审查 Python 代码时
---
# Python Style Baseline

## Rule

### 风格

- 遵循 [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) 中与团队常用版本兼容的条款（类型注解、命名、docstring 结构等按指南取舍）。
- 注释（含 `#` 与说明性 docstring）一律**简体中文**。
- **模块级 / 类级 docstring**：若用户未要求 API 文档生成，可用**简短中文**说明；更详细的说明优先用 `#` 行注释，避免大块模板化 docstring。

### 命名

- 类名使用 PascalCase；函数名 / 变量名 / 参数名使用 snake_case；常量命名按指南约定执行。
- 标准库与第三方库符号保持原名，不做重命名。

## Applies To

- Python 源码与相关评审

## Not For

- 非 Python 语言风格
