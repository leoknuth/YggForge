---
id: 20260701163140-kr$$$$-csb$$$$$-vhsf
title: C++ Style Baseline
type: rule
status: active
confidence: high
scope: C++ source style and related review comments
last_reviewed: 2026-07-14
owners:
  - team
tags:
  - cpp
  - style
keywords:
  - pragma once
  - pointer style
  - reference style
  - 注释风格
related:
  - 20260701165030-kr$$$$-cb$$$$$$-qppv
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 当任务涉及 C++ 代码风格、注释风格、头文件写法、指针与引用写法时优先加载
---
# C++ Style Baseline

## 语言标准

- 使用 **C++11**；不要使用 C++11 之后的语言特性（如 `optional`（C++17）、结构化绑定等），除非用户明确要求更高标准。
- 若涉及编译命令，默认以 `-std=c++11` 为基准向用户说明。
- 在与 C++11 不冲突的前提下，遵循 [Google C++ Style Guide](https://google.github.io/styleguide/cppguide.html)。

## 注释

- 注释默认使用简体中文
- 不使用 Doxygen 式 `/** ... */` 作为类/函数说明主格式
- 成员变量注释不使用 `///<` 这类尾随写法
- 成员变量说明统一使用上一行 `//`

## 头文件

- 统一使用 `#pragma once`
- 不使用 `#ifndef / #define` 风格 include guard

## 指针与引用

- 统一写作 `Type* p`
- 统一写作 `Type& r`
- 即 `*`、`&` 贴类型，不贴变量名

## 逻辑段注释模板

较长逻辑段使用三行模板：

```cpp
// --------------------------------------------------------------------------------
// 一行段落概述或标题
// --------------------------------------------------------------------------------
```

较小逻辑段和成员分组使用单行模板：

```cpp
// --- 简短注释 ---
```

## 命名

- 类型 / 类名使用 PascalCase
- 函数名与变量名使用 snake_case
- 常量命名按 Google C++ Style Guide 约定执行
- 标准库与第三方库符号保持原名

## Applies To

- C++ 代码与相关评审

## Not For

- 业务架构决策
- 非 C++ 语言风格

## 待补充

- include 顺序
- RAII 与资源所有权表达
- 错误处理策略
- 并发原语使用约束
- `noexcept` / `constexpr` / `[[nodiscard]]` 使用习惯
