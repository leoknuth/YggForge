---
id: 20260714144840-kr$$$$-$$$$$$$$-77lt
title: 工作区格式配置遵循
type: rule
status: active
confidence: high
source: agent-profile
scope: 写代码前遵循工作区已有格式配置
last_reviewed: 2026-07-14
owners:
  - team
tags:
  - formatting
  - editorconfig
  - clang-format
keywords:
  - .editorconfig
  - .clang-format
related:
  - 20260701163140-kr$$$$-csb$$$$$-vhsf
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 在任意工作区执行写代码 / 改代码 / 改文本文件前
always_apply: true
projection_mode: sync
projection:
  - profiles/cursor/rules/workspace-format.mdc
---
# 工作区格式配置遵循

## Rule

- 先检查工作区根目录是否存在 `.editorconfig`。
- 若存在 `.editorconfig`，必须遵循其缩进、行尾空白、换行等约束，不引入与其冲突的手工格式。
- 对 C/C++ 文件，若工作区根目录存在 `.clang-format`，必须遵循其格式规则。
- 当 `.editorconfig` 与 `.clang-format` 同时存在时：
  - 通用编辑行为优先按 `.editorconfig`；
  - C/C++ 专项排版（括号、换行、空格风格等）按 `.clang-format`。

## Applies To

- 所有会改写源码或文本文件的任务

## Not For

- 用户明确要求忽略本地格式配置的一次性实验
