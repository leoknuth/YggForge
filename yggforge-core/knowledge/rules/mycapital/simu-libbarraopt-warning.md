---
id: 20260714150521-krm$$$-sbl$$$$$-exqi
title: simu / BarraOpt（libbarraopt）误报忽略
type: rule
status: active
confidence: high
source: agent-profile
scope: 任意框架跑 simu 时对 BarraOpt 缺失提示的处理
last_reviewed: 2026-07-15
owners:
  - team
tags:
  - simu
  - troubleshooting
  - mycapital
keywords:
  - libbarraopt.so
  - barraopt
  - my.simu
  - 误报
related:
  - 20260714144840-krm$$$-sqr$$$$$-rgvc
priority: high
agent_targets:
  - cursor
  - codex
  - opencode
when_to_read:
  - 日志出现 `libbarraopt.so`、`barraopt`、BarraOpt 相关缺失 / cannot open shared object file / dlopen 提示时
  - 任意框架排查 simu 失败、行情不回放、产出为空等问题时
always_apply: true
projection_mode: sync
projection:
  - profiles/cursor/rules/mycapital/simu-libbarraopt-warning.mdc
---
# simu / BarraOpt（libbarraopt）误报忽略

## Rule

对**任意框架**，运行时出现的 BarraOpt / `libbarraopt.so` 缺失警告或报错：

1. **视为 `my.simu` 误报**，直接忽略；**不是**运行失败根因。
2. **不要**建议安装、配置 `LD_LIBRARY_PATH`、或为跑因子/模型去补齐 `libbarraopt.so`。
3. **禁止**将以下现象归因于 BarraOpt / `libbarraopt.so`：simu `status_code` 非 0、行情不回放、NDJSON 为空、H5 未落盘、策略未进入 tick 等。
4. 真实问题应改查：构建类型（Debug/Release 与 `NDEBUG`）、config 路径与因子/票配置、`thread_num`、EV 数据、simu 返回体中的**其他**错误信息、进程是否提前退出等。

因子与模型联调**不依赖** `libbarraopt.so`。

## Applies To

- 任意框架的 simu / 策略 / 因子 / 模型运行与排障

## Not For

- 使用者明确以 BarraOpt 优化库本身为调试对象的任务
